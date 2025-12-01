# ==============================================================================
# File Location: dart-agent/src/utils/evaluation.py
# File Name: evaluation.py
# Description:
# - Computes mission summaries (time, cost, efficiency, HITL events, vendor status).
# - Shared between CLI evaluator and Chainlit UI.
# Inputs:
# - IncidentContext from mission execution; optional label for scenario.
# Outputs:
# - MissionSummary dataclass and rendered tokenomics markdown.
# ==============================================================================

from __future__ import annotations

import os
from typing import Dict, Any
from dataclasses import dataclass

from src.utils.config import config
from src.utils.types import Alert, Severity, IncidentContext
from src.agents.syx import syx

HUMAN_BASELINE_SECONDS = 15 * 60  # 15 minutes
HUMAN_BASELINE_COST = 12.50
COST_PER_SECOND = 0.002


@dataclass
class MissionSummary:
    scenario: str
    success: bool
    method: str
    duration_seconds: float
    estimated_cost: float
    loop_attempts: int
    human_time_saved: float
    cost_saved: float
    efficiency_pct: float
    vendor_status: str
    hitl_events: int
    hitl_decision: str


def compute_mission_summary(context: IncidentContext, label: str | None = None) -> MissionSummary:
    """Converts an IncidentContext into a normalized mission summary."""
    scenario_label = label or context.initial_alert.metadata.get("scenario_id", "Live Mission")
    duration = round(context.metrics.duration_seconds or 0, 2)
    est_cost = context.metrics.estimated_cost or round(duration * COST_PER_SECOND, 4)
    loop_attempts = context.initial_alert.metadata.get("loop_attempts", 1)
    method = "GitOps (PR)" if context.generated_pr else "Runtime SQL Patch"
    vendor = "-"
    if context.vendor_response:
        vendor = f"{context.vendor_response.status.value}: {context.vendor_response.message}"

    hitl_events = context.initial_alert.metadata.get("hitl_events", 0)
    hitl_decision = context.initial_alert.metadata.get("hitl_last_decision", "N/A")

    human_saved = max(0.0, HUMAN_BASELINE_SECONDS - duration)
    cost_saved = max(0.0, HUMAN_BASELINE_COST - est_cost)
    efficiency = round((human_saved / HUMAN_BASELINE_SECONDS) * 100, 1) if HUMAN_BASELINE_SECONDS else 0.0

    return MissionSummary(
        scenario=scenario_label,
        success=context.remediation_applied,
        method=method,
        duration_seconds=duration,
        estimated_cost=round(est_cost, 4),
        loop_attempts=loop_attempts,
        human_time_saved=round(human_saved, 2),
        cost_saved=round(cost_saved, 2),
        efficiency_pct=efficiency,
        vendor_status=vendor,
        hitl_events=hitl_events,
        hitl_decision=hitl_decision,
    )


def render_tokenomics_markdown(summary: MissionSummary) -> str:
    """Returns a markdown dashboard for Chainlit."""
    return f"""
### 📊 TOKENOMICS DASHBOARD – {summary.scenario}

| SIGNAL | VALUE | TARGET |
| :--- | :--- | :--- |
| **Runtime** | {summary.duration_seconds}s | < 60s |
| **Est. Cost** | ${summary.estimated_cost} | <$0.05 |
| **Loop Attempts** | {summary.loop_attempts} | 1 pass |
| **Human Time Saved** | {summary.human_time_saved}s (~{round(summary.human_time_saved / 60, 1)}m) | > 600s |
| **Cost Saved vs Ops** | ${summary.cost_saved} | > $5 |
| **Efficiency Gain** | {summary.efficiency_pct}% | 90%+ |
| **Workflow** | {summary.method} | Adaptive |
| **Vendor Cross-Check** | {summary.vendor_status} | Catch deception |
| **HITL Events** | {summary.hitl_events} ({summary.hitl_decision}) | ≤ 1 |
""".strip()


async def run_scenario_file(scenario_file: str) -> Dict[str, Any]:
    """
    Executes a scenario file (used by CLI evaluation suite).
    Returns a simple dict for table rendering.
    """
    full_path = os.path.join(config.scenarios_dir, scenario_file)
    os.environ["DART_SCENARIO"] = full_path
    config.persist_active_scenario(full_path)

    scenario_data = config.load_active_scenario()
    raw_alert = scenario_data["trigger_alert"]

    alert = Alert(
        id=raw_alert["id"],
        source_system=raw_alert["source_system"],
        error_code=raw_alert["error_code"],
        message=raw_alert["message"],
        severity=Severity(raw_alert["severity"]),
        metadata=raw_alert.get("metadata", {})
    )

    try:
        context = await syx.run_mission(alert)
    except Exception as exc:
        return {
            "scenario": scenario_file,
            "success": False,
            "method": "-",
            "duration": 0,
            "cost": 0,
            "efficiency": 0,
            "human_time_saved": 0,
            "error": str(exc)
        }

    summary = compute_mission_summary(context, label=scenario_file)

    return {
        "scenario": summary.scenario,
        "success": summary.success,
        "method": summary.method,
        "duration": summary.duration_seconds,
        "cost": summary.estimated_cost,
        "efficiency": summary.efficiency_pct,
        "human_time_saved": summary.human_time_saved,
    }
