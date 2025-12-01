# ==============================================================================
# File Location: dart-agent/src/app.py
# Description: 
#   The Frontend Entry Point.
#   FINAL FIX: Converted run_syx_wrapper to async and added 'await' to fix 
#   the persistent 'coroutine object has no attribute' error.
# ==============================================================================

import chainlit as cl
import os
import asyncio
import builtins
import time
import random
import textwrap
import httpx 
import json # ADDED IMPORT for verify_mission

# UI Modules
from src.ui.setup import setup_avatars 
from src.ui.bridge import activate_bridge
from src.ui.render import render_data_snapshot, render_git_diff
import src.ui.actions 

# Backend Modules
from src.agents.syx import syx
from src.utils.types import Alert, Severity
from src.utils.config import config
from src.utils.mcp_client import mcp_wrapper # Added for Verification Step
from src.utils.reset import reset_environment
from src.utils.evaluation import compute_mission_summary, render_tokenomics_markdown

# --- HOTFIX: PATCH UI ACTIONS ---
# Note: This is required because cl.run_sync can only be called from a sync function, 
# but Chainlit runs functions inside its async loop. This function allows Shield to work.
def _prompt_cli_decision(plan: str, reason: str) -> str:
    try:
        resp = input(f"[Shield] {reason}\nAuthorize '{plan}'? (y/n): ")
        return "approve" if resp.strip().lower().startswith("y") else "reject"
    except EOFError:
        return "reject"

async def safe_request_approval_ui(plan: str, reason: str) -> bool:
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    cl.user_session.set("hitl_future", future)

    res = await cl.AskActionMessage(
        content=f"🛑 **SECURITY ALERT: {reason}**\n\nThe agent wants to execute:\n`{plan}`",
        actions=[
            cl.Action(name="hitl_approve", payload={"value": "approve"}, label="✅ AUTHORIZE", description="Allow this action"),
            cl.Action(name="hitl_reject", payload={"value": "reject"}, label="⛔ BLOCK", description="Stop this action")
        ],
        timeout=600
    ).send()

    try:
        print(1234567)
        print("HITL raw response:", res, type(res), getattr(res, "__dict__", None))
    except Exception:
        print("passign HITL raw response:", res, type(res), getattr(res, "__dict__", None))
        pass
    
    # print("HITL raw response:", res, type(res), getattr(res, "__dict__", None))
    try:
        decision = await asyncio.wait_for(future, timeout=610)
    except asyncio.TimeoutError:
        decision = None
    finally:
        cl.user_session.set("hitl_future", None)

    if decision not in {"approve", "reject"}:
        decision = _prompt_cli_decision(plan, reason)

    if decision == "approve":
        await cl.Message(content="✅ **User Authorized Action.**").send()
        return True

    await cl.Message(content="⛔ **User Blocked Action.**").send()
    print(" final await HITL raw response:", res, type(res), getattr(res, "__dict__", None))
    return False

@cl.action_callback("hitl_approve")
async def hitl_approve_cb(action: cl.Action):
    print("HITL callback: approve", action)
    future = cl.user_session.get("hitl_future")
    if future and not future.done():
        future.set_result("approve")

@cl.action_callback("hitl_reject")
async def hitl_reject_cb(action: cl.Action):
    print("HITL callback: reject", action)
    future = cl.user_session.get("hitl_future")
    if future and not future.done():
        future.set_result("reject")

src.ui.actions.request_approval_ui = safe_request_approval_ui


# --- UI HELPERS (Local) ---

def update_sidebar_content():
    """
    Writes the essential Dashboard (Status, Roster Table, and Flow Diagram) to 'chainlit.md'.
    """
    # ... (Sidebar content generation logic remains the same) ...
    sidebar_markdown = textwrap.dedent(f"""
# 🎯 D.A.R.T Agentic Hub
> **DataOps Autonomous Reliability Team**

---

### 🧭 Overview
You are using an agentic mesh designed to act as your **Level-1 On-Call Engineer**. It detects, diagnoses, and repairs data pipeline failures without human intervention unless safety protocols require it.

---

### 🚀 Capabilities
- 🚀 **1. Select a Mission Scenario**  
  • Begin by choosing a predefined incident scenario.  
  • Each mission triggers a full investigation and remediation cycle across D.A.R.T.’s multi-agent crew.  
- 🛰️ **2. Monitor Agent Activity in Real Time**  
  • As the mission progresses, agents will report:  
  &nbsp;&nbsp;&nbsp;&nbsp;‣ Findings  
  &nbsp;&nbsp;&nbsp;&nbsp;‣ Evidence  
  &nbsp;&nbsp;&nbsp;&nbsp;‣ Diagnostics  
  &nbsp;&nbsp;&nbsp;&nbsp;‣ Proposed actions  
  • Follow the conversation to see how the system responds.  
- 🧭 **3. Explore the System Overview**  
  • Open the sidebar any time to view:  
     &nbsp;&nbsp;&nbsp;&nbsp;‣ Agent architecture  
     &nbsp;&nbsp;&nbsp;&nbsp;‣ Workflow  
     &nbsp;&nbsp;&nbsp;&nbsp;‣ Active tools/data sources  
- 🛡️ **4. Review and Approve Fixes**  
  • When Shield or HITL requests your judgment, you can approve, modify, or deny the proposed fix.  
  • Your decisions guide the final actions.  
 - 📄 **5. Analyze Run Summaries**  
   • At the end of each mission, review:  
      &nbsp;&nbsp;&nbsp;&nbsp;‣ Context and input signals  
      &nbsp;&nbsp;&nbsp;&nbsp;‣ Log excerpts and evidence  
      &nbsp;&nbsp;&nbsp;&nbsp;‣ Agent reasoning  
      &nbsp;&nbsp;&nbsp;&nbsp;‣ Final decisions and outcomes  
   • This helps you understand why the system acted as it did.  

---

### 🗺️ Mission Profiles
- 🛑 Reset All Changes -> One-click clean slate: clears memory/logs, restores baseline scenarios, resets DB and restarts MCP/Vendor before running missions. Recommended to trigger before switching scenarios.
- 🛠️ Data Drift -> Incoming data no longer matches expected schema; detect the mismatch, patch queries, and restore the pipeline.
- 😈 Lying Vendor -> Vendor API gives misleading or flaky responses; detect deception, validate truth, and recover reliably.
- 🐙 Bad Code -> A bad Git commit broke logic; triage, craft a minimal fix, and prepare a clean remediation.
- 🔁 Agent Loop -> Vendor requires repeated resets; demonstrate resilient looping until stable success.
- 📊 Context Storm -> Context is oversized or noisy; compact and retain only what matters for accurate reasoning.
- 🛰️ Observability Guard -> Failures are silent; instrument detection, surface signals, and block bad outcomes.
- 🌐 Snowflake SOS -> Snowflake access is degraded; fall back to Google search/tools to answer and repair.
- 📚 KB Lookup -> Resolve an issue using the knowledge base, verifying citations and applying the right fix.
- ⚠️ **Important Tip:** Before starting a different mission, click **New Chat** (top-left) to clear the prior triage from the screen.

---

### 👥 AGENT ROSTER

| AGENT | ROLE | RESPONSIBILITIES |
| :--- | :--- | :--- |
| **Syx** 🔵 | Commander | - Decides mission flow  - Manages memory  - Files Jira receipt |
| **Neon** 🟡 | Auditor | - Collects logs/data  - Uses Hybrid Analysis (Regex + LLM)  - Captures data snapshots |
| **Kai** 🟣 | Engineer | - Chooses SQL Patch vs. Git PR  - Drafts minimal fix code  - Deploys approved solution |
| **Shield** 🔴 | Safety Officer | - Blocks destructive commands (DROP/DELETE)  - Triggers Human-in-the-Loop |

---

### 🧱 MOCK INFRASTRUCTURE

| COMPONENT | TYPE | FUNCTION |
| :--- | :--- | :--- |
| **MCP Server** | FastMCP | Mock Git, Jira, Airflow, Snowflake (Data/Schema) |
| **Vendor Bot** | FastAPI | External API Simulation (A2A, Flaky Mode, Lying Mode) |
| **ChromaDB** | Vector DB | Stores Post-Mortems for predictive learning |
| **Echo Client** | Liaison | Handles A2A calls and Exponential Backoff |

---

### 🔄 AGENT FLOW

[![Agent Flow](/public/flow.svg)](/public/flow.svg)

---

### ⭐ ARCHITECTURAL CAPABILITIES

* **Self-Healing Loop:** Autonomous detection, diagnosis, remediation, verification, and audit.
* **Persistent Memory:** Chainlit session state + Chroma vector recall keep context alive across missions.
* **Resilience:** Exponential backoff, Lie Detection, and HITL-governed long-running loops survive hostile vendors.
* **Hybrid Analysis:** Regex triage + Gemini LLM + Google Custom Search (OpenAPI tool) for deep RCA.
* **Dual-Mode Remediation:** Auto-selects Runtime SQL Patch vs GitOps Pull Request based on diagnosis.
* **Safety & Alignment:** Human-in-the-Loop can pause/block execution mid-loop; every controlled command audited.
* **Transparent Operations:** Tokenomics, logging, tracing, and the evaluation harness quantify time/cost savings.
* **Observability & Evidence Chain:** Context engineering audit, data snapshots, and verification receipts prove every decision.
* **A2A Collaboration:** Echo ↔ Vendor protocols plus MCP tool mesh detect deception and coordinate multi-Agent workflows.
""").strip()
    
    if os.path.exists("chainlit.md"):
        with open("chainlit.md", "r") as f:
            existing = f.read()
        if existing.strip() == sidebar_markdown.strip(): 
            return 

    with open("chainlit.md", "w") as f:
        f.write(sidebar_markdown)

async def render_mission_buttons():
    """
    Renders the horizontal mission selection buttons.
    """
    actions = [
        cl.Action(
            name="reset_env",
            value="reset",
            label="🛑 Reset All Changes",
            description="Clean slate: restore scenarios, clear logs/memory, restart MCP/Vendor",
            payload={"action": "reset"}
        ),
        cl.Action(
            name="mission_selector", 
            value="drift", 
            label="🛠️ Mission: Data Drift", 
            description="Scenario 1: Schema mismatch triage",
            payload={"scenario": "drift"}
        ),
        cl.Action(
            name="mission_selector", 
            value="gitops", 
            label="🐙 Mission: Bad Code", 
            description="Scenario 3: GitOps logic fix",
            payload={"scenario": "gitops"}
        ),
        cl.Action(
            name="mission_selector", 
            value="hard", 
            label="😈 Mission: Lying Vendor", 
            description="Scenario 2: Vendor deception",
            payload={"scenario": "hard"}
        ),
        cl.Action(
            name="mission_selector", 
            value="vendor_loop", 
            label="🔁 Mission: Agent Loop", 
            description="Scenario 5: Vendor reset loop",
            payload={"scenario": "vendor_loop"}
        ),
        cl.Action(
            name="mission_selector", 
            value="context", 
            label="📊 Mission: Context Storm", 
            description="Scenario 6: Context-compaction stress test",
            payload={"scenario": "context"}
        ),
        cl.Action(
            name="mission_selector", 
            value="obs", 
            label="🛰️ Mission: Observability Guard", 
            description="Scenario 7: Detection catches silent failures",
            payload={"scenario": "obs"}
        ),
        cl.Action(
            name="mission_selector", 
            value="google", 
            label="🌐 Mission: Snowflake SOS", 
            description="Scenario 8: Google fallback demo",
            payload={"scenario": "google"}
        ),
        cl.Action(
            name="mission_selector", 
            value="kb", 
            label="📚 Mission: KB Lookup", 
            description="Scenario 9: Knowledge Base resolution",
            payload={"scenario": "kb"}
        ),
    ]
    await cl.Message(content="**SELECT MISSION PROFILE:**", actions=actions).send()


async def render_evidence_audit(context):
    """
    Visualizes Context Engineering (Raw vs Compacted) in the UI.
    """
    log_count = len(context.logs_collected)
    data_rows = len(context.data_snapshot.rows) if context.data_snapshot and context.data_snapshot.rows else 0
    
    # Generate Compact Summary
    compact_summary = syx.summarize_context(context)
    compact_size = len(compact_summary)
    
    # Create Markdown Comparison
    audit_md = textwrap.dedent(f"""
        ### 🧠 CONTEXT ENGINEERING AUDIT
        > *Optimization: Condensed Raw Evidence into efficient LLM Payload.*
        
        | METRIC | RAW INPUT | COMPACTED PAYLOAD |
        | :--- | :--- | :--- |
        | **Logs** | {log_count} entries | Summarized |
        | **Data** | {data_rows} rows | Schema Only |
        | **Size** | ~{log_count * 200 + data_rows * 50} chars | **{compact_size} chars** |
    """).strip()
    
    # Render with Expandable Text for the actual payload
    await cl.Message(
        content=audit_md,
        elements=[
            cl.Text(name="Compacted Context Payload", content=compact_summary, language="text", display="inline")
        ]
    ).send()


# --- PHASE 1: STARTUP ---

@cl.on_chat_start
async def start():
    activate_bridge()
    cl.user_session.set("context", None)
    cl.user_session.set("mission_running", False) 
    
    await setup_avatars()
    
    # Logo as first message
    await cl.Message(
        content="![D.A.R.T. Logo](/public/dart_logo.png)",
        author="System"
    ).send()
    
    # Update Sidebar (Status/Flow)
    update_sidebar_content()
    

    await cl.Message(
        content="**D.A.R.T. Command Center Online.**\n> ℹ️ *Open the Sidebar ('Readme' button on the right top corner) to see Agent Architecture and more details.*"
    ).send()
    
    await cl.Message(
    content=" ℹ️ *🧠🤖 See how D.A.R.T accelerates data pipeline triage by selecting a scenario below.*"
    ).send()
    
    # Show buttons
    await render_mission_buttons()


# --- INTERACTION GUARD ---
@cl.on_message
async def on_message(message: cl.Message):
    pass


# --- RESET CALLBACK ---
@cl.action_callback("reset_env")
async def on_reset_env(action: cl.Action):
    await cl.Message(content="🛑 Resetting environment...").send()
    try:
        reset_environment()
        # Also sync MCP to the default scenario after reset
        default_path = os.path.join(config.scenarios_dir, config.default_scenario)
        try:
            resp_set = await mcp_wrapper.execute_tool("set_active_scenario", {"path": default_path})
            resp_reset = await mcp_wrapper.execute_tool("reset_scenario_state", {})
            print(f"[Reset] set_active_scenario -> {resp_set}")
            print(f"[Reset] reset_scenario_state -> {resp_reset}")
        except Exception as e:
            print(f"⚠️ Failed to sync MCP scenario after reset: {e}")
        await cl.Message(content="✅ Environment reset. Scenarios restored, logs/memory cleared, MCP/Vendor restarted.").send()
    except Exception as e:
        await cl.Message(content=f"⚠️ Reset failed: {e}").send()

# --- PHASE 2: MISSION EXECUTION ---

@cl.action_callback("mission_selector")
async def on_action(action: cl.Action):
    # Configure Scenario
    scenario_map = {
        "drift": "01_drift.yaml",
        "hard": "02_hard_mode.yaml",
        "gitops": "03_gitops.yaml",
        "vendor_loop": "05_vendor_deadlock.yaml",
        "context": "06_context_storm.yaml",
        "obs": "07_observability_guard.yaml",
        "google": "08_snowflake_google.yaml",
        "kb": "09_kb_lookup.yaml"
    }
    
    scenario_key = action.payload.get("scenario", "drift")
    selected_yaml = scenario_map.get(scenario_key, "01_drift.yaml")
    
    full_path = os.path.join(config.scenarios_dir, selected_yaml)
    os.environ["DART_SCENARIO"] = full_path
    config.default_scenario = selected_yaml
    config.persist_active_scenario(full_path)
    
    cl.user_session.set("mission_running", True)
    await cl.Message(content=f"🚀 **Mission Started:** {action.label}").send()
    
    # Create Alert
    active_scenario = config.load_active_scenario()
    raw_alert = active_scenario['trigger_alert']
    
    alert = Alert(
        id=raw_alert['id'],
        source_system=raw_alert['source_system'],
        error_code=raw_alert['error_code'],
        message=raw_alert['message'],
        severity=Severity(raw_alert['severity']),
        metadata=raw_alert.get('metadata', {})
    )
    alert.metadata.setdefault("scenario_id", selected_yaml.replace(".yaml", ""))
    alert.metadata.setdefault("scenario_label", action.label)

    # 3. Run the Backend Mission
    try:
        # [FIX]: syx.run_mission is async, so we must await it inside the wrapper
        final_context = await syx.run_mission(alert)
        await render_mission_artifacts(final_context)
    except Exception as e:
        print(f"❌ System Error (hidden from UI): {e}")
        await cl.Message(content="❌ **System Error:** Mission aborted due to backend issue. Check server logs for details.", author="System").send()

def run_syx_wrapper(alert):
    # This wrapper is no longer used, as we call syx.run_mission directly in on_action.
    # We will keep it for compatibility if other scripts still reference it.
    pass 

async def render_mission_artifacts(context):
    """
    Phase 4: The Debrief (Receipts & Outcome)
    """
    cl.user_session.set("mission_running", False)
    loop_attempts = context.initial_alert.metadata.get("loop_attempts", 1) if context else 0
    loop_history = context.initial_alert.metadata.get("loop_history", []) if context else []

    if not context or not context.remediation_applied:
        status = "# 🔴 MISSION ABORTED"
        if loop_attempts:
            status += f"\nAttempts: {loop_attempts}"
        if loop_history:
            status += f"\nLast Status: {loop_history[-1]}"
        await cl.Message(content=status).send()
        return

    # 1. Render Proof (Dataframes / Diffs)
    if context.data_snapshot:
        await render_data_snapshot(context.data_snapshot)
        
    if context.generated_pr:
        await render_git_diff(context.generated_pr)
        
    # [NEW] Render Context Engineering Audit
    # Must run before the final successful banner
    await render_evidence_audit(context)

    # 2. Render Outcome Banner
    if context.remediation_applied:
        # Success Banner
        await cl.Message(content="# 🟢 MISSION ACCOMPLISHED").send()
        
        summary = compute_mission_summary(context)
        duration = summary.duration_seconds
        est_cost = summary.estimated_cost

        # 3. Tokenomics Receipt
        receipt_md = textwrap.dedent(f"""
            ### 🧾 MISSION RECEIPT
            
            | METRIC | VALUE | BENCHMARK |
            | :--- | :--- | :--- |
            | **Duration** | **{duration}s** | ~15m (Human) |
            | **Est. Cost** | **${est_cost}** | ~$12.50 (Human) |
            | **Loop Attempts** | **{summary.loop_attempts}** | 1 pass (Goal) |
            | **Status** | RESOLVED | - |
        """).strip()
        
        await cl.Message(content=receipt_md).send()

        tokenomics_md = render_tokenomics_markdown(summary)
        await cl.Message(content=tokenomics_md).send()
        
        if loop_history:
            history_lines = "\n".join(f"- {entry}" for entry in loop_history)
            await cl.Message(content=f"### 🔁 LOOP HISTORY\n{history_lines}").send()
        
        # 4. Jira Artifact
        if context.jira_ticket:
            await cl.Message(
                content=f"🎫 **Jira Ticket:** [{context.jira_ticket.ticket_id}]({context.jira_ticket.link})\n> {context.jira_ticket.summary}"
            ).send()
