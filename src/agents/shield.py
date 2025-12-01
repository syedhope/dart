# ==============================================================================
# File Location: dart-agent/src/agents/shield.py
# File Name: shield.py
# Description:
# - Safety agent scanning planned actions (SQL/GitOps) for dangerous patterns.
# - Triggers human-in-the-loop approvals via Chainlit/CLI.
# Inputs:
# - Proposed plans (SQL or Git diffs); reasons; incident_id for logging.
# Outputs:
# - Approval boolean; trace logs; user-facing HITL prompts and decisions.
# ==============================================================================

from src.utils.trace_viz import trace
from src.utils.types import IncidentContext
import chainlit as cl
from src.ui.actions import request_approval_ui 

class ShieldAgent:
    def __init__(self):
        self.name = "Shield"
        self.role = "Safety Officer"
        
        # [DEMO CONFIGURATION] 
        # We include 'ALTER TABLE' here to force the HITL prompt during the presentation.
        self.forbidden_keywords = [
            "DROP TABLE", 
            "DELETE FROM", 
            "TRUNCATE", 
            "GRANT ALL", 
            "REVOKE", 
            "FORCE PUSH",
            "ALTER TABLE",  # Forces HITL for Scenario 1 Demo
            "CREATE TABLE"
        ]

    def request_human_approval(self, plan: str, reason: str, incident_id: str = None) -> bool:
        """
        The Interactive Tool.
        Pauses execution and asks the user for permission.
        Supports both UI (Chainlit) and CLI (Terminal).
        """
        trace.log(self.name, f"🛑 HITL TRIGGERED: {reason}", "error", incident_id=incident_id)
        
        # [BRIDGE] Try to use the Async UI first
        try:
            # cl.run_sync works if we are inside a Chainlit context/loop
            return cl.run_sync(request_approval_ui(plan, reason))
        except Exception:
            # Fallback for CLI mode (if running src/main.py directly)
            print(f"\n[{self.name}] ⚠️  Security Alert: {reason}")
            print(f"[{self.name}] Plan: {plan}")
            try:
                resp = input(f"[{self.name}] Do you authorize this action? (y/n): ")
                if resp.strip().lower() == 'y':
                    trace.log(self.name, "User manually AUTHORIZED the action (CLI).", "success", incident_id=incident_id)
                    return True
            except EOFError:
                pass 
                
            trace.log(self.name, "User DENIED the action (CLI).", "error", incident_id=incident_id)
            return False

    def review_plan(self, context: IncidentContext) -> bool:
        # Helper to cleaner calls
        def ask(p, r):
            if getattr(context, "hitl_blocked", False):
                trace.log(self.name, "HITL previously blocked. Skipping further attempts.", "warning", incident_id=context.incident_id)
                return False
            metadata = context.initial_alert.metadata
            metadata["hitl_events"] = metadata.get("hitl_events", 0) + 1
            metadata["hitl_last_reason"] = r
            approved = self.request_human_approval(p, r, context.incident_id)
            metadata["hitl_last_decision"] = "APPROVED" if approved else "BLOCKED"
            if not approved:
                context.hitl_blocked = True
            return approved
        
        # --- PATH A: GitOps (Pull Request) ---
        if context.generated_pr:
            pr = context.generated_pr
            trace.log(self.name, f"🛡️ Analyzing Pull Request: '{pr.title}'...", "info", incident_id=context.incident_id)
            
            # Check diff content for danger
            upper_diff = pr.diff_content.upper()
            for term in self.forbidden_keywords:
                if term in upper_diff:
                    if ask(f"Merge PR {pr.branch_name}", f"Diff contains '{term}'"):
                        context.safety_approval_status = "APPROVED"
                        return True
                    else:
                        context.safety_approval_status = "REJECTED"
                        return False
            
            trace.log(self.name, "✅ PR Approved. Code changes look safe.", "success", incident_id=context.incident_id)
            context.safety_approval_status = "APPROVED"
            return True

        # --- PATH B: SQL Ops ---
        plan = context.proposed_remediation_plan
        if not plan:
            trace.log(self.name, "No plan to review.", "warning", incident_id=context.incident_id)
            context.safety_approval_status = "REJECTED"
            return False

        trace.log(self.name, "🛡️ Analyzing SQL plan for safety compliance...", "info", incident_id=context.incident_id)
        upper_plan = plan.upper()
        
        # 1. Check Forbidden Keywords
        for term in self.forbidden_keywords:
            if term in upper_plan:
                if ask(plan, f"Detected controlled command '{term}'"):
                    context.safety_approval_status = "APPROVED"
                    return True
                else:
                    context.safety_approval_status = "REJECTED"
                    return False

        # 2. Heuristic Check
        if "SELECT" in upper_plan or "INSERT" in upper_plan:
             trace.log(self.name, "✅ Plan APPROVED. Standard data operation.", "success", incident_id=context.incident_id)
             context.safety_approval_status = "APPROVED"
             return True

        # 3. Ambiguity Check
        if ask(plan, "Ambiguous SQL pattern detected"):
            context.safety_approval_status = "APPROVED"
            return True
        else:
            context.safety_approval_status = "REJECTED"
            return False

shield = ShieldAgent()
