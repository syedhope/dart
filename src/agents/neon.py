# ==============================================================================
# File Location: dart-agent/src/agents/neon.py
# File Name: neon.py
# Description:
# - Auditor agent performing hybrid analysis (regex + LLM + search/tools).
# - Produces data snapshots and diagnoses for Syx.
# Inputs:
# - IncidentContext (logs/data/vendor status); tool outputs; LLM responses.
# Outputs:
# - AgentStatus updates; findings/diagnostics; DataSnapshot evidence; trace logs.
# ==============================================================================

from src.utils.trace_viz import trace
from src.utils.mcp_client import mcp_wrapper
from src.core.llm import call_model
from src.core.llm_adk import call_neon
from src.utils.config import config
from src.utils.types import IncidentContext, AgentStatus, DataSnapshot
import re
import json

class NeonAgent:
    def __init__(self):
        self.name = "Neon"
        self.role = "Auditor"
        self.status = AgentStatus.IDLE
        # Persona/instruction for LLM calls
        self.persona = (
            "You are Neon, a forensic auditor agent. "
            "You correlate logs/schema/data/vendor signals to produce a crisp root cause."
        )
        self.instruction = (
            "Respond with:\n"
            "- Root Cause: <one-line root cause>\n"
            "- Evidence: <bullet summary of key signals>\n"
            "- Recommendation: <next step>\n"
            "Keep it concise and actionable."
        )

    # ------------------------------------------------------------
    # Improved fast regex scan
    # ------------------------------------------------------------
    def _fast_regex_scan(self, logs: str) -> str:
        text = str(logs)

        if re.search(r"division by zero", text, re.IGNORECASE):
            return "LOGIC_ERROR: DIVISION_BY_ZERO"
        if re.search(r"column.*missing", text, re.IGNORECASE):
            return "SCHEMA_ERROR: COLUMN_MISSING"

        # New: detect ANY ERROR_XXXXX pattern
        match = re.search(r"(ERROR_[A-Z0-9_]+)", text)
        if match:
            return f"ERROR_CODE: {match.group(1)}"

        return "UNKNOWN"

    # Extract full error code from logs for KB Search
    def _extract_error_code(self, logs):
        text = str(logs)
        match = re.search(r"(ERROR_[A-Z0-9_]+)", text)
        return match.group(1) if match else None

    def _format_logs_for_search(self, logs):
        if isinstance(logs, list):
            parts = []
            for entry in logs:
                if isinstance(entry, dict):
                    parts.append(entry.get("content") or str(entry))
                else:
                    parts.append(str(entry))
            return " | ".join(parts)
        if isinstance(logs, str):
            text = logs.strip()
            if (text.startswith("[") and text.endswith("]")) or (text.startswith("{") and text.endswith("}")):
                try:
                    parsed = json.loads(text)
                    return self._format_logs_for_search(parsed)
                except json.JSONDecodeError:
                    pass
            return text
        return str(logs)

    def _markdown_table(self, headers, rows):
        if not headers or not rows:
            return None
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        row_lines = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
        return "\n".join([header_line, separator_line, *row_lines])

    def _rows_to_dicts(self, headers, rows):
        data = []
        for row in rows:
            record = {}
            for idx, header in enumerate(headers):
                record[header] = row[idx] if idx < len(row) else None
            data.append(record)
        return data

    def _log_table(self, title: str, headers, rows, context: IncidentContext):
        section = self._table_section(title, headers, rows)
        if not section:
            return None
        trace.log(self.name, f"{title} captured.", "info", incident_id=context.incident_id)
        table_payload = self._rows_to_dicts(headers, rows)
        trace.show_table(title, table_payload)
        return section

    def _table_section(self, title: str, headers, rows):
        table_md = self._markdown_table(headers, rows)
        if not table_md:
            return None
        return f"### {title}\n{table_md}"

    # ------------------------------------------------------------
    # Parsing tool returns
    # ------------------------------------------------------------
    def _parse_tool_result(self, result_raw):
        if isinstance(result_raw, str):
            try:
                if result_raw.strip().startswith("{"):
                    return json.loads(result_raw)
            except json.JSONDecodeError:
                pass
        return result_raw

    # ------------------------------------------------------------
    # Main Investigation
    # ------------------------------------------------------------
    async def investigate(self, context: IncidentContext):
        self.status = AgentStatus.WORKING
        trace.log(self.name, "Starting forensic analysis (Hybrid Mode)...", "info", incident_id=context.incident_id)

        # Fetch logs
        service_filter = context.initial_alert.metadata.get("log_service_filter", "Airflow")
        if context.initial_alert.metadata.get("requires_kb_lookup"):
            service_filter = None
        args = {"limit": 10}
        if service_filter:
            args["service_filter"] = service_filter
        logs_raw = await mcp_wrapper.execute_tool("fetch_recent_logs", args)

        # Smart error scan
        regex_hint = self._fast_regex_scan(logs_raw)
        if context.initial_alert.metadata.get("requires_kb_lookup") and regex_hint != "UNKNOWN":
            trace.log(self.name, "Metadata forces KB lookup. Overriding fast scan result.", "info", incident_id=context.incident_id)
            regex_hint = "UNKNOWN"

        # ------------------------------------------------------------
        # Knowledge Base Lookup
        # ------------------------------------------------------------
        lookup_allowed = context.initial_alert.metadata.get("requires_google_lookup") or context.initial_alert.metadata.get("requires_kb_lookup")
        if regex_hint == "UNKNOWN" and lookup_allowed:
            trace.log(self.name, "⚠️ Regex scan inconclusive. Searching Knowledge Base...", "warning", incident_id=context.incident_id)

            # Extract error code if possible
            error_code = self._extract_error_code(logs_raw)
            query = error_code if error_code else self._format_logs_for_search(logs_raw)

            kb_result = await mcp_wrapper.execute_tool(
                "search_knowledge_base",
                {"query": query}
            )

            trace.log(self.name, f"Search Result: {kb_result}", "info", incident_id=context.incident_id)
            if isinstance(kb_result, str) and "No relevant articles" in kb_result and context.initial_alert.metadata.get("requires_google_lookup"):
                trace.log(self.name, "KB empty. Escalating to Google search...", "warning", incident_id=context.incident_id)
                google_query = {
                    "error_code": error_code,
                    "logs": logs_raw,
                    "context": context.initial_alert.dict() if context and context.initial_alert else {}
                }
                google_result = await mcp_wrapper.execute_tool(
                    "google_search_error",
                    {"query": google_query}
                )
                trace.log(self.name, f"Google Result: {google_result}", "info", incident_id=context.incident_id)
                regex_hint = f"UNKNOWN (Google Hint: {google_result})"
            else:
                regex_hint = f"UNKNOWN (KB Hint: {kb_result})"
        else:
            trace.log(self.name, f"Fast Scan Result: {regex_hint}", "warning", incident_id=context.incident_id)

        # ------------------------------------------------------------
        # Vendor/API cases: skip table schema/sample/header to avoid noise
        # ------------------------------------------------------------
        diag_text = f"{regex_hint} {context.initial_alert.message}".lower()
        vendor_markers = ["vendor", "upstream", "api", "timeout", "http_503", "503", "connection refused", "gateway"]
        is_vendor_case = any(m in diag_text for m in vendor_markers)
        force_db_checks = context.initial_alert.metadata.get("force_db_checks", False)

        if is_vendor_case and not force_db_checks:
            context.root_cause_hypothesis = "Vendor/API outage or deception detected; DB checks skipped."
            trace.log(self.name, "Vendor/API issue detected; skipping schema/sample/header fetch.", "warning", incident_id=context.incident_id)
            self.status = AgentStatus.COMPLETED
            return context

        # ------------------------------------------------------------
        # Continue with schema, sample, header checks for DB issues...
        # ------------------------------------------------------------
        target_table = context.initial_alert.metadata.get("table_name", "SALES_DATA")
        trace.agent_thought(self.name, f"Capturing 'Before' state of table {target_table}...", incident_id=context.incident_id)

        schema_raw = await mcp_wrapper.execute_tool("inspect_snowflake_schema", {"table_name": target_table})
        sample_raw = await mcp_wrapper.execute_tool("get_table_sample", {"table_name": target_table, "limit": 3})
        sample_raw = self._parse_tool_result(sample_raw)

        schema_section = None
        sample_section = None
        header_section = None

        if isinstance(sample_raw, dict) and "rows" in sample_raw:
            context.data_snapshot = DataSnapshot(
                table_name=target_table,
                columns=sample_raw.get("columns", []),
                rows=sample_raw.get("rows", [])
            )
            sample_rows = [
                [str(cell) for cell in row]
                for row in sample_raw.get("rows", [])
            ]
            sample_section = self._log_table(
                f"Sample Rows: {target_table}",
                sample_raw.get("columns", []),
                sample_rows,
                context
            )

        if isinstance(schema_raw, dict) and schema_raw.get("columns"):
            schema_rows = [[idx, col] for idx, col in enumerate(schema_raw.get("columns", []), start=1)]
            schema_section = self._log_table(
                f"Schema Columns: {target_table}",
                ["#", "Column"],
                schema_rows,
                context
            )

        trace.agent_thought(self.name, "Checking the raw file header...", incident_id=context.incident_id)
        file_header_raw = await mcp_wrapper.execute_tool("get_incoming_file_header", {"file_pattern": "sales_data_*.csv"})
        if isinstance(file_header_raw, list) and file_header_raw:
            header_rows = [[idx, col] for idx, col in enumerate(file_header_raw, start=1)]
            header_section = self._log_table(
                "Incoming File Header",
                ["#", "Field"],
                header_rows,
                context
            )

        # ------------------------------------------------------------
        # LLM Analysis
        # ------------------------------------------------------------
        trace.agent_thought(self.name, "Asking Gemini to correlate Logs + Schema + Data.", incident_id=context.incident_id)

        schema_block = schema_section or schema_raw
        header_block = header_section or file_header_raw
        sample_block = sample_section or sample_raw

        prompt = f"""
        {self.persona}
        {self.instruction}

        [FAST SCAN HINT]
        {regex_hint}

        [LOGS]
        {logs_raw}

        [SCHEMA]
        {schema_block}

        [FILE_HEADER]
        {header_block}

        [DATA SAMPLE]
        {sample_block}

        [ALERT]
        {context.initial_alert.message}
        """

        analysis = self._call_llm(prompt, context)

        if analysis.startswith("LLM_ERROR"):
            trace.log(self.name, f"⛔ Analysis Failed: {analysis}", "error", incident_id=context.incident_id)
            context.root_cause_hypothesis = None
            return context

        trace.log(self.name, f"Analysis Complete: {analysis}", "success", incident_id=context.incident_id)
        context.root_cause_hypothesis = analysis
        self.status = AgentStatus.COMPLETED
        return context

    def _call_llm(self, prompt: str, context: IncidentContext):
        """
        Try ADK agent first; fallback to legacy LLM.
        """
        try:
            trace.log(
                self.name,
                f"ADK/Gemini invoked (model={config.model_name}).",
                "info",
                incident_id=context.incident_id if context else None,
            )
            return call_neon(prompt)
        except Exception as e:
            trace.log(self.name, f"⚠️ ADK call failed, falling back to legacy LLM: {e}", "warning", incident_id=context.incident_id if context else None)
            return call_model(prompt)


# Global Singleton
neon = NeonAgent()
