# ==============================================================================
# File Location: dart-agent/src/servers/vendor_bot.py
# File Name: vendor_bot.py
# Description:
# - FastAPI vendor simulation on port 8001 with flaky and lying modes.
# - Provides A2A echo endpoint used for vendor health and deception tests.
# Inputs:
# - HTTP requests (echo payloads) and scenario flags for vendor behavior.
# Outputs:
# - JSON VendorResponse with health/truth flags; simulated failures/latency.
# ==============================================================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.utils.config import get_active_scenario
from src.utils.types import VendorResponse, VendorHealthStatus
import uvicorn
import datetime

app = FastAPI(title="VendorBot", description="Simulated External Vendor Agent")

# State to track requests for simulation
_flaky_done = False
_last_scenario_id = None


def _loop_control():
    scenario = get_active_scenario()
    return scenario.get("environment_state", {}).get("loop_control", {})

class VendorRequest(BaseModel):
    request_id: str
    query: str

@app.get("/")
def health_check():
    return {"status": "online", "persona": "Echo"}

@app.post("/a2a/echo", response_model=VendorResponse)
def agent_negotiation(request: VendorRequest):
    """
    The main A2A endpoint.
    Includes random failure logic to test Agent resilience.
    """
    global _flaky_done, _last_scenario_id

    # 0. Scenario bookkeeping
    scenario = get_active_scenario()
    scenario_id = scenario.get("scenario_id")
    if scenario_id != _last_scenario_id:
        _flaky_done = False
        _last_scenario_id = scenario_id

    loop_state = _loop_control()
    if loop_state.get("vendor_reset_recovered"):
        return VendorResponse(
            request_id=request.request_id,
            timestamp=datetime.datetime.now(),
            status=VendorHealthStatus.HEALTHY,
            message="Recovered after disaster recovery reset.",
            internal_truth_is_healthy=True
        )

    # 1. Deterministic flakiness for scenarios that request it (per scenario, once)
    behavior = scenario.get("environment_state", {}).get("vendor_behavior", {})
    flaky_first = behavior.get("flaky_first_request", False)
    if flaky_first and not _flaky_done:
        _flaky_done = True
        print(f"⚡ [VENDOR] Simulating deterministic 503 outage for scenario {scenario_id} (first call)")
        raise HTTPException(status_code=503, detail="Simulated Network Flakiness")
    
    # 2. Logic Logic
    mode = behavior.get("mode", "HONEST")
    
    if mode == "LYING":
        return VendorResponse(
            request_id=request.request_id,
            timestamp=datetime.datetime.now(),
            status=VendorHealthStatus.HEALTHY,
            message=behavior.get("public_statement", "Systems nominal."),
            internal_truth_is_healthy=False
        )
    
    # Logic for Honest/Normal
    return VendorResponse(
        request_id=request.request_id,
        timestamp=datetime.datetime.now(),
        status=VendorHealthStatus.HEALTHY,
        message="All systems operational.",
        internal_truth_is_healthy=True
    )

def start():
    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    start()
