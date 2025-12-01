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