# ==============================================================================
# File Location: dart-agent/src/agents/echo_client.py
# File Name: echo_client.py
# Description:
# - Liaison to the vendor bot with retry/backoff and health checks.
# - Provides status polling and A2A queries for vendor interactions.
# Inputs:
# - Incident IDs for logging; vendor endpoints from config; HTTP responses.
# Outputs:
# - VendorResponse objects with status/message; trace logs of vendor connectivity.
# ==============================================================================

import httpx
from src.utils.types import VendorResponse, VendorHealthStatus
from src.utils.trace_viz import trace
from src.utils.retry_utils import with_backoff
from src.utils.config import config 
import uuid

class EchoClient:
    def __init__(self):
        self.name = "Echo"
        self.role = "Liaison"
        self.base_url = config.vendor_api_url

    def _create_error_response(self) -> VendorResponse:
        return VendorResponse(
            request_id="error",
            status=VendorHealthStatus.OUTAGE,
            message="Failed to contact vendor (max retries)."
        )

    @with_backoff(retries=3, base_delay=1.0, exceptions=(httpx.HTTPError, httpx.RequestError))
    async def _check_status_with_retry(self, incident_id: str) -> VendorResponse:
        trace.log(self.name, f"Connecting to Vendor at {self.base_url}...", "info", incident_id=incident_id)
        
        payload = {
            "request_id": str(uuid.uuid4()),
            "query": "STATUS_CHECK"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/a2a/echo", json=payload, timeout=5.0)
            response.raise_for_status() 
            
            data = response.json()
            vendor_resp = VendorResponse(**data)
            
            status_color = "success" if vendor_resp.status == VendorHealthStatus.HEALTHY else "error"
            trace.log(self.name, f"Vendor Reply: {vendor_resp.status} | '{vendor_resp.message}'", status_color, incident_id=incident_id)
            
            return vendor_resp

    async def check_vendor_status(self, incident_id: str) -> VendorResponse:
        try:
            return await self._check_status_with_retry(incident_id)
        except Exception as e:
            trace.log(self.name, f"Connection Failed (Max Retries Exceeded): {str(e)}", "error", incident_id=incident_id)
            return self._create_error_response()

echo_client = EchoClient()
