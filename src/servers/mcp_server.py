# ==============================================================================
# File Location: dart-agent/src/servers/mcp_server.py
# File Name: mcp_server.py
# Description:
# - Mock enterprise MCP server exposing data/code/ops/search tools.
# - Simulates Snowflake, GitHub, Jira, KB via FastMCP on port 8000.
# Inputs:
# - Scenario data from config (environment state, datasets, KB, files).
# Outputs:
# - MCP tool responses for logs/data/SQL/KB/code/echo tests used by agents.
# ==============================================================================

from fastmcp import FastMCP
from src.utils.config import get_active_scenario, config
from typing import List, Dict, Any, Optional
import re
import random
import copy
import httpx
import json

mcp = FastMCP("MockEnterprise", port=8000)

_SCENARIO_CACHE = {"id": None, "data": None}

def _current_scenario():
    data = get_active_scenario()
    scenario_id = data.get("scenario_id")
    if _SCENARIO_CACHE["id"] != scenario_id:
        _SCENARIO_CACHE["id"] = scenario_id
        _SCENARIO_CACHE["data"] = copy.deepcopy(data)
    return _SCENARIO_CACHE["data"] or {}

def _env_state():
    return _current_scenario().get("environment_state", {})

def _loop_control():
    return _env_state().get("loop_control", {})

@mcp.tool()
def reset_scenario_state() -> Dict[str, str]:
    """
    Reloads the active scenario from disk and clears any in-memory mutations
    (e.g., schema changes from previous missions). Use this before each mission
    to ensure a clean, scenario-aligned state.
    """
    _SCENARIO_CACHE["id"] = None
    _SCENARIO_CACHE["data"] = None
    fresh = _current_scenario()
    scenario_id = fresh.get("scenario_id")
    print(f"🔄 [MCP] Scenario state reset for {scenario_id}")
    return {"status": "RESET", "scenario_id": scenario_id or "unknown", "message": "Scenario state reloaded from active scenario."}

@mcp.tool()
def set_active_scenario(path: str) -> Dict[str, str]:
    """
    Updates the active scenario path (shared via persisted file) and reloads it immediately.
    """
    try:
        # Update env for this process so get_active_scenario() picks up the new path.
        import os
        os.environ["DART_SCENARIO"] = path
        # Persist for other processes reading the cache file.
        config.persist_active_scenario(path)
        _SCENARIO_CACHE["id"] = None
        _SCENARIO_CACHE["data"] = None
        fresh = _current_scenario()
        scenario_id = fresh.get("scenario_id")
        print(f"📂 [MCP] Active scenario set to {path} (id={scenario_id})")
        return {"status": "OK", "scenario_id": scenario_id or "unknown", "path": path}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

# --- DATA DOMAIN (Snowflake) ---

@mcp.tool()
def fetch_recent_logs(service_filter: str = None, limit: int = 10) -> List[Dict]:
    scenario = _current_scenario()
    env = scenario.get("environment_state", {})
    logs_data = env.get("logs", [])
    scenario_id = scenario.get("scenario_id")
    filtered_logs = []
    for log in logs_data:
        if service_filter and service_filter.lower() not in log["service"].lower():
            continue
        filtered_logs.append(log)
    return filtered_logs[:limit]

@mcp.tool()
def inspect_snowflake_schema(table_name: str) -> Dict:
    schema_def = _env_state().get("snowflake_schema", {})
    if schema_def.get("table") == table_name:
        return {
            "table": table_name,
            "columns": schema_def.get("columns", [])
        }
    return {"error": f"Table {table_name} not found."}

@mcp.tool()
def get_incoming_file_header(file_pattern: str) -> List[str]:
    return _env_state().get("incoming_file_header", {}).get("columns", [])

@mcp.tool()
def get_table_sample(table_name: str, limit: int = 3) -> Dict:
    schema = _env_state().get("snowflake_schema", {})
    if schema.get("table") != table_name:
         return {"error": f"Table {table_name} not found"}
    
    columns = schema.get("columns", [])
    rows = []
    for i in range(limit):
        row = []
        for col in columns:
            if "id" in col: row.append(i + 101)
            elif "date" in col: row.append("2025-01-01")
            elif "amount" in col: row.append(round(150.00 + (i * 10.5), 2))
            elif "region" in col: row.append("US-EAST")
            else: row.append(f"mock_{col}_{i}")
        rows.append(row)
    
    return {"table": table_name, "columns": columns, "rows": rows}

@mcp.tool()
def deploy_sql_patch(sql_statement: str, environment: str = "PROD") -> Dict:
    print(f"⚡ [MOCK DB] Executing Patch: {sql_statement}")
    
    loop_ctrl = _loop_control()
    require_reset = loop_ctrl.get("require_vendor_reset")
    reset_done = loop_ctrl.get("vendor_reset_recovered")
    if require_reset and not reset_done:
        return {
            "status": "FAILED",
            "error": "Stage table locked by vendor sync. Run reset_vendor_cursor first."
        }
    if loop_ctrl.get("force_observability_failure"):
        return {"status": "SUCCESS", "message": "Mock deploy reported success (obs guard mode)." }

    if "DROP" in sql_statement.upper():
        return {"status": "FAILED", "error": "Safety Policy Violation: DROP blocked."}
    
    if "ALTER TABLE" in sql_statement.upper() and "ADD" in sql_statement.upper():
        try:
            # Remove IF NOT EXISTS for parsing
            clean_sql = sql_statement.replace("IF NOT EXISTS", "")
            col_match = re.search(r"ADD\s+(?:COLUMN\s+)?(\w+)", clean_sql, re.IGNORECASE)

            if col_match:
                new_col = col_match.group(1).lower()
                schema = _env_state().get("snowflake_schema", {})
                
                if schema:
                    current_cols = schema.get("columns", [])
                    if new_col not in current_cols:
                        current_cols.append(new_col)
                        schema["columns"] = current_cols 
                        print(f"   ✅ Schema Updated! Table now has columns: {current_cols}")
                        return {"status": "SUCCESS", "message": f"Column '{new_col}' added.", "rows_affected": 1}
                    else:
                         return {"status": "SUCCESS", "message": f"Column '{new_col}' already exists.", "rows_affected": 0}
        except:
            pass
    return {"status": "SUCCESS", "message": "Query executed (No state change)."}

# --- GIT DOMAIN (Mock GitHub) ---

@mcp.tool()
def get_file_content(repo_name: str, file_path: str) -> str:
    repo_files = _env_state().get("repo_files", {})
    content = repo_files.get(file_path)
    if content:
        return content
    return f"Error: File {file_path} not found in {repo_name}"

@mcp.tool()
def create_branch(repo_name: str, base_branch: str, new_branch: str) -> Dict:
    print(f"🌲 [MOCK GIT] Created branch '{new_branch}' from '{base_branch}'")
    return {"status": "SUCCESS", "branch": new_branch}

@mcp.tool()
def open_pull_request(repo_name: str, title: str, description: str, branch_name: str) -> Dict:
    pr_id = random.randint(1000, 9999)
    print(f"🐙 [MOCK GIT] PR #{pr_id} Opened: {title}")
    return {
        "status": "OPEN", 
        "pr_id": str(pr_id),
        "link": f"https://github.mock/{repo_name}/pull/{pr_id}",
        "diff_stat": "+5 / -2 lines"
    }

# --- OPS DOMAIN (Mock Jira) ---

@mcp.tool()
def create_jira_ticket(project_key: str, summary: str, priority: str = "Medium") -> Dict:
    ticket_id = f"{project_key}-{random.randint(100, 999)}"
    print(f"🎫 [MOCK JIRA] Ticket Created: {ticket_id} ({summary})")
    return {
        "status": "SUCCESS",
        "ticket_id": ticket_id,
        "link": f"https://jira.mock/browse/{ticket_id}"
    }

# --- KNOWLEDGE DOMAIN (Mock Google Search) ---

@mcp.tool()
def search_knowledge_base(query: str) -> str:
    """
    Smart KB search for error codes inside logs.
    Looks up articles embedded in the active scenario.
    """
    scenario = _current_scenario()
    kb_entries = scenario.get("environment_state", {}).get("knowledge_base", [])
    query_text = str(query or "")
    query_upper = query_text.upper()
    print(f"🔍 [SEARCH] Querying Knowledge Base: {query_text}")

    error_code = None
    match = re.search(r"(ERROR_[A-Z0-9_]+)", query_upper)
    if match:
        error_code = match.group(1)

    for entry in kb_entries:
        ref = entry.get("query")
        article = entry.get("article")
        if not ref or not article:
            continue
        if ref.upper() in query_upper or (error_code and ref.upper() in error_code):
            return article

    return "No relevant articles found."

def _logs_to_string(logs: Any) -> str:
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
                return _logs_to_string(parsed)
            except json.JSONDecodeError:
                pass
        return text
    return str(logs)

@mcp.tool()
def google_search_error(query: Any) -> str:
    """
    Simulates a Google search fallback for unknown errors.
    """
    query_text = ""
    if isinstance(query, dict):
        error_code = query.get("error_code")
        logs = query.get("logs")
        segments = []
        if error_code:
            segments.append(str(error_code))
        if logs:
            segments.append(_logs_to_string(logs))
        query_text = " | ".join(segments) if segments else ""
    else:
        query_text = str(query or "")
    print('google',query)
    if config.google_custom_search_key and config.google_cx_id:
        try:
            params = {
                "key": config.google_custom_search_key,
                "cx": config.google_cx_id,
                "q": query_text
            }
            print("🔍 Google query:", query_text)
            resp = httpx.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            print("🔍 Google query:", data)
            items = data.get("items", [])
            if items:
                top = items[0]
                snippet = top.get("snippet", "")
                title = top.get("title", "")
                link = top.get("link", "")
                return f"Google: {title} - {snippet} ({link})"
            
            return "Google: No results found."
        except Exception as e:
            return f"Google search failed: {e}"

    query_upper = query_text.upper()
    GOOGLE_MAP = {
        "SNOWFLAKE_ERR_8001": "Google result: Create helper function DERIVE_SPEND or replace it with SPEND * 1.0."
        ,
        "SNOWFLAKE_STREAM_60779": "Google result: Stream offsets can be advanced; see https://stackoverflow.com/questions/60779268/snowflake-data-pipeline-problems-in-particular-stream-issue",
        "SNOWFLAKE_UNSUPPORTED_FUNCTION": "Google result: Snowflake equivalent of generate_series is TABLE(GENERATOR(...)) or SEQ4() - https://stackoverflow.com/questions/54348801/generate-series-equivalent-in-snowflake"
    }
    for key, value in GOOGLE_MAP.items():
        if key in query_upper:
            return value
    return "Google result: Community thread suggests checking Snowflake UDF definitions."

# --- OPERATIONS DOMAIN (Vendor Reset) ---

@mcp.tool()
def reset_vendor_cursor(reason: str = "manual") -> Dict:
    loop_ctrl = _loop_control()
    if not loop_ctrl.get("require_vendor_reset"):
        return {
            "status": "SKIPPED",
            "message": "Vendor reset not required in current scenario."
        }
    if loop_ctrl.get("vendor_reset_recovered"):
        return {
            "status": "ALREADY_RESET",
            "message": "Vendor cursor already reset."
        }
    loop_ctrl["vendor_reset_recovered"] = True
    print(f"🔄 [VENDOR] Cursor reset triggered via MCP (reason={reason}).")
    return {
        "status": "RESET",
        "message": "Vendor cursor rewound. Stage locks cleared."
    }

if __name__ == "__main__":
    print(f"Starting Omni-Server MCP on Port 8000 (SSE Mode)...")
    mcp.run(transport="sse")
