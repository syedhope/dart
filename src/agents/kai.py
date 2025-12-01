# ==============================================================================
# File Location: dart-agent/src/agents/kai.py
# File Name: kai.py
# Description:
# - Remediator agent selecting SQL vs GitOps fixes and executing tools asynchronously.
# - Parses tool responses robustly and logs actions per incident.
# Inputs:
# - IncidentContext with diagnosis, file path, and metadata; tool outputs; LLM responses.
# Outputs:
# - Draft remediation plans (SQL or GitPR), status updates, and trace logs.
# ==============================================================================

from src.utils.trace_viz import trace
from src.utils.mcp_client import mcp_wrapper
from src.core.llm import call_model
from src.core.llm_adk import call_kai
from src.utils.config import config
from src.utils.types import IncidentContext, AgentStatus, GitPR
import json

class KaiAgent:
    def __init__(self):
        self.name = "Kai"
        self.role = "Remediator"
        self.status = AgentStatus.IDLE
        # Persona/instruction for LLM calls
        self.persona = (
            "You are Kai, a remediation engineer. "
            "Choose minimal, safe fixes (SQL or Git) aligned to the diagnosis."
        )
        self.instruction_sql = (
            "Return a single Snowflake SQL command. No comments. No prose. "
            "Prefer additive changes (ALTER ... ADD) or targeted updates only."
        )
        self.instruction_git = (
            "Return ONLY the fixed code block. No prose, no comments. "
            "Keep changes minimal and aligned to the diagnosis."
        )

    async def run_disaster_recovery(self, context: IncidentContext) -> bool:
        """
        Executes a vendor disaster recovery reset via MCP.
        """
        trace.log(self.name, "Executing vendor disaster recovery (cursor reset)...", "warning", incident_id=context.incident_id)
        result_raw = await mcp_wrapper.execute_tool("reset_vendor_cursor", {
            "reason": f"vendor_dr_{context.incident_id[:8]}"
        })
        result = self._parse_tool_result(result_raw)

        if isinstance(result, dict) and result.get("status") in {"RESET", "ALREADY_RESET"}:
            trace.log(self.name, f"Vendor DR success: {result}", "success", incident_id=context.incident_id)
            context.proposed_remediation_plan = "Vendor disaster recovery reset"
            context.remediation_applied = True
            return True

        trace.log(self.name, f"Vendor DR failed or skipped: {result}", "error", incident_id=context.incident_id)
        return False

    def _is_vendor_issue(self, context: IncidentContext, diagnosis: str) -> bool:
        diag = (diagnosis or "").lower()
        code = (context.initial_alert.error_code or "").lower()
        meta = context.initial_alert.metadata or {}
        endpoint = str(meta.get("endpoint", "")).lower()

        # For KB/force_db_checks/disable_drift missions, do not treat as vendor/API
        if meta.get("requires_kb_lookup") or meta.get("force_db_checks") or meta.get("disable_drift"):
            return False

        vendor_markers = [
            "vendor",
            "upstream",
            "api",
            "timeout",
            "http_503",
            "503",
            "connection refused",
            "gateway"
        ]
        return (
            any(marker in diag for marker in vendor_markers)
            or code.startswith("http_")
            or "http" in endpoint
        )

    def _parse_tool_result(self, result_raw):
        if isinstance(result_raw, str):
            try:
                if result_raw.strip().startswith("{"):
                    return json.loads(result_raw)
            except json.JSONDecodeError:
                pass
        return result_raw

    async def generate_fix(self, context: IncidentContext):
        self.status = AgentStatus.WORKING
        trace.log(self.name, "Analyzing diagnosis to select remediation strategy...", "info", incident_id=context.incident_id)

        diagnosis = context.root_cause_hypothesis
        if not diagnosis:
            return None

        mission_name = (context.initial_alert.metadata or {}).get("mission_name", "").lower()
        expected_fix = (context.initial_alert.metadata or {}).get("expected_fix", "").lower()

        # Agent Loop: prefer stage cleanup / deadlock relief instead of drift or vendor DR
        if expected_fix == "stage_cleanup" or "agent loop" in mission_name:
            target_table = context.initial_alert.metadata.get("table_name", "SALES_DATA")
            sql_plan = (
                f"DELETE FROM {target_table} "
                "USING (SELECT id, ROW_NUMBER() OVER (PARTITION BY id ORDER BY date DESC) AS rn FROM {table}) dedup "
                f"WHERE {target_table}.id = dedup.id AND dedup.rn > 1"
            )
            # Fix formatting placeholder
            sql_plan = sql_plan.replace("{table}", target_table)
            trace.log(self.name, f"Strategy Selected: STAGE CLEANUP (Agent Loop) -> {sql_plan}", "warning", incident_id=context.incident_id)
            context.proposed_remediation_plan = sql_plan
            return sql_plan

        if self._is_vendor_issue(context, diagnosis):
            trace.log(
                self.name,
                "Vendor/API issue detected; skipping SQL/GitOps generation. Returning control to Syx/loop.",
                "warning",
                incident_id=context.incident_id,
            )
            context.proposed_remediation_plan = None
            return None

        missing_cols = context.initial_alert.metadata.get("missing_columns") if context and context.initial_alert else None
        if missing_cols:
            # Deterministic schema drift fix: add missing columns as VARCHAR
            target_table = context.initial_alert.metadata.get("table_name", "SALES_DATA")
            statements = [
                f"ALTER TABLE {target_table} ADD COLUMN IF NOT EXISTS {col} VARCHAR"
                for col in missing_cols
            ]
            sql_plan = ";\n".join(statements)
            trace.log(self.name, f"Strategy Selected: RUNTIME SQL PATCH (Schema Drift) -> {sql_plan}", "warning", incident_id=context.incident_id)
            context.proposed_remediation_plan = sql_plan
            return sql_plan

        file_path = context.initial_alert.metadata.get("file_path")
        if file_path or "division by zero" in diagnosis.lower():
            return await self._handle_gitops_fix(context, file_path, diagnosis)
        
        return self._handle_sql_fix(context, diagnosis)

    def _handle_sql_fix(self, context: IncidentContext, diagnosis: str):
        trace.log(self.name, "Strategy Selected: RUNTIME SQL PATCH", "warning", incident_id=context.incident_id)
        
        prompt = f"""
        {self.persona}
        [DIAGNOSIS] {diagnosis}
        [INSTRUCTION] {self.instruction_sql}
        """
        sql_plan = self._call_llm(prompt, context).strip().replace("```sql", "").replace("```", "").strip()
        
        if sql_plan.startswith("LLM_ERROR"):
             trace.log(self.name, f"⛔ Generation Failed: {sql_plan}", "error", incident_id=context.incident_id)
             return None
             
        trace.log(self.name, f"Proposed SQL: {sql_plan}", "warning", incident_id=context.incident_id)
        context.proposed_remediation_plan = sql_plan
        return sql_plan

    async def _handle_gitops_fix(self, context: IncidentContext, file_path: str, diagnosis: str):
        trace.log(self.name, "Strategy Selected: GITOPS CODE FIX", "warning", incident_id=context.incident_id)
        
        repo_name = "analytics-pipeline"
        if not file_path:
            file_path = "models/kpi/roi_calc.sql"
            
        trace.agent_thought(self.name, f"Reading source code from {file_path}...", incident_id=context.incident_id)
        source_code = await mcp_wrapper.execute_tool("get_file_content", {"repo_name": repo_name, "file_path": file_path})
        
        trace.agent_thought(self.name, "Drafting code patch...", incident_id=context.incident_id)
        prompt = f"""
        {self.persona}
        [BUG] {diagnosis}
        [FILE: {file_path}]
        {source_code}
        {self.instruction_git}
        """
        fixed_code = self._call_llm(prompt, context).strip().replace("```sql", "").replace("```", "").strip()

        pr = GitPR(
            title=f"Fix: {context.initial_alert.error_code}",
            branch_name=f"fix/{context.incident_id[:8]}",
            diff_content=fixed_code,
            repo_name=repo_name
        )
        
        trace.log(self.name, f"Proposed PR: {pr.title} on branch {pr.branch_name}", "warning", incident_id=context.incident_id)
        context.generated_pr = pr
        context.proposed_remediation_plan = f"Merge PR: {pr.title}" 
        return pr

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
            return call_kai(prompt)
        except Exception as e:
            trace.log(self.name, f"⚠️ ADK call failed, falling back to legacy LLM: {e}", "warning", incident_id=context.incident_id if context else None)
            return call_model(prompt)

    async def execute_fix(self, context: IncidentContext) -> bool:
        if context.generated_pr:
            pr = context.generated_pr
            trace.log(self.name, f"🚀 Opening Pull Request on {pr.repo_name}...", "warning", incident_id=context.incident_id)
            
            await mcp_wrapper.execute_tool("create_branch", {
                "repo_name": pr.repo_name, "base_branch": "main", "new_branch": pr.branch_name
            })
            
            result_raw = await mcp_wrapper.execute_tool("open_pull_request", {
                "repo_name": pr.repo_name, "title": pr.title, "description": "Auto-fix", "branch_name": pr.branch_name
            })
            
            result = self._parse_tool_result(result_raw)
            link = result.get('link', 'Unknown Link') if isinstance(result, dict) else result
            trace.log("GitHub", f"PR Opened: {link}", "success", incident_id=context.incident_id)
            
            await mcp_wrapper.execute_tool("create_jira_ticket", {"project_key": "DATA", "summary": f"Fix {context.initial_alert.error_code}"})
            
            context.remediation_applied = True
            return True

        if context.proposed_remediation_plan:
            trace.log(self.name, f"🚀 Deploying Patch to Production...", "warning", incident_id=context.incident_id)
            result_raw = await mcp_wrapper.execute_tool("deploy_sql_patch", {"sql_statement": context.proposed_remediation_plan})
            
            result = self._parse_tool_result(result_raw)
            
            if isinstance(result, str) and (result.startswith("Error") or "FAILED" in result):
                trace.log("MCP", f"Deployment Failed: {result}", "error", incident_id=context.incident_id)
                return False

            if isinstance(result, dict) and result.get("status") == "FAILED":
                 trace.log("MCP", f"Deployment Rejected: {result.get('error')}", "error", incident_id=context.incident_id)
                 return False

            trace.log("MCP", f"Deployment Result: {result}", "success", incident_id=context.incident_id)
            context.remediation_applied = True
            return True
            
        return False

# Global Singleton
kai = KaiAgent()
