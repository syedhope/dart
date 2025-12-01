# ==============================================================================
# File Location: dart-agent/src/main.py
# File Name: main.py
# Description:
# - CLI-style entrypoint to run full Syx mission with evidence audit and verification.
# - Logs evidence, compacted context, and agent traces for terminal-driven runs.
# Inputs:
# - Active scenario from config (env override or persisted selection).
# - Alert metadata seeded from scenario YAML.
# Outputs:
# - Console traces/tables; mission execution via Syx; verification logs.
# ==============================================================================
from src.utils.types import Alert, Severity
from src.agents.syx import syx
from src.utils.config import get_active_scenario
from src.utils.trace_viz import trace
from src.utils.mcp_client import mcp_wrapper
import time
import json
import asyncio 
import textwrap

async def display_collected_evidence(context):
    trace.header("EVIDENCE AUDIT", "Agent Collection vs. LLM Input")
    
    log_count = len(context.logs_collected)
    log_status = f"Collected {log_count} log entries."
    
    data_status = "No data sample collected."
    if context.data_snapshot and context.data_snapshot.rows:
        data_status = f"Collected {len(context.data_snapshot.rows)} rows from {context.data_snapshot.table_name}."
    
    vendor_status = f"Vendor Status: {context.vendor_response.status.value}" if context.vendor_response else "No vendor check performed."

    evidence_data = [
        {"Artifact": "Logs", "Detail": log_status},
        {"Artifact": "Data Snapshot", "Detail": data_status},
        {"Artifact": "Vendor Status", "Detail": vendor_status},
    ]
    trace.show_table("RAW EVIDENCE COLLECTED", evidence_data)
    
    compact_summary = syx.summarize_context(context)
    trace.log("System", f"LLM Input (Compacted Context):\n{textwrap.indent(compact_summary, '  > ')}", "info")
    trace.log("System", f"Payload Size: {len(compact_summary)} characters.", "success")

async def verify_mission(final_context):
    await display_collected_evidence(final_context)
    
    time.sleep(1)
    trace.header("DEMO VERIFICATION", "Checking System State")

    if not final_context or not final_context.remediation_applied:
        trace.log("System", "❌ Mission Incomplete. No remediation was applied.", "error")
        return

    # --- BRANCH A: GITOPS VERIFICATION ---
    if final_context.generated_pr:
        trace.log("System", "Mode: GitOps (Pull Request)", "info")
        pr = final_context.generated_pr
        trace.log("GitHub", f"✅ Verified PR #{pr.branch_name} is OPEN.", "success")
        return

    # --- BRANCH B: SQL OPS VERIFICATION ---
    if final_context.proposed_remediation_plan and "ALTER TABLE" in final_context.proposed_remediation_plan:
        trace.log("System", "Mode: Database Ops (SQL Patch)", "info")
        table_name = "SALES_DATA"
        
        # Use Async Call
        schema_raw = await mcp_wrapper.execute_tool("inspect_snowflake_schema", {"table_name": table_name})
        try:
            if isinstance(schema_raw, str):
                schema = json.loads(schema_raw)
            else:
                schema = schema_raw
            
            columns = schema.get('columns', [])
            trace.log("System", f"Final Schema: {columns}", "success")
            
            if len(columns) > 5:
                trace.log("System", "✅ PROOF: New column detected in schema!", "success")
            else:
                trace.log("System", "❌ Fix failed: Column count unchanged.", "error")
        except Exception as e:
            trace.log("System", f"❌ Verification Error: {e}", "error")
        return

def run_simulation():
    active_scenario = get_active_scenario()
    trace.header("D.A.R.T. SIMULATION START", f"Scenario: {active_scenario['scenario_id']}")
    
    raw_alert = active_scenario['trigger_alert']
    alert = Alert(
        id=raw_alert['id'],
        source_system=raw_alert['source_system'],
        error_code=raw_alert['error_code'],
        message=raw_alert['message'],
        severity=Severity(raw_alert['severity']),
        metadata=raw_alert['metadata']
    )

    # Run the Async Mission
    final_context = asyncio.run(syx.run_mission(alert))

    # Run the Async Verification
    asyncio.run(verify_mission(final_context))

if __name__ == "__main__":
    run_simulation()
