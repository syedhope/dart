# ==============================================================================
# File Location: dart-agent/src/servers/startup.py
# File Name: startup.py
# Description:
# - Launchpad to start MCP server and VendorBot processes and verify readiness.
# - Performs health checks and checkpoint echo test with retries.
# Inputs:
# - Ports from hardcoded defaults/config; environment python executable.
# Outputs:
# - Running MCP/Vendor processes; console logs of health; exit codes on failure.
# ==============================================================================

import multiprocessing
import time
import requests
import sys
import os

# Import the server runners
from src.servers import vendor_bot

def run_mcp_server():
    """Wrapper to run the MCP server."""
    # Using sys.executable ensures we use the same python env
    os.system(f"{sys.executable} -m src.servers.mcp_server")

def run_vendor_server():
    """Wrapper to run the VendorBot (FastAPI)."""
    vendor_bot.start()

def wait_for_port(port: int, name: str, retries=15):
    """Polls a localhost port until it accepts connections."""
    print(f"   Waiting for {name} on port {port}...")
    for _ in range(retries):
        try:
            # We use a simple GET. For FastMCP SSE, the root / often returns 404 or specific content, 
            # but connecting proves it's listening.
            requests.get(f"http://localhost:{port}/", timeout=1)
            print(f"   ✅ {name} is online!")
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            continue
    print(f"   ❌ {name} failed to start.")
    return False

def verify_vendor_echo(retries=3):
    """
    Performs the Checkpoint test with Retries.
    Handles the 30% random failure rate of the VendorBot.
    """
    print("\n" + "="*40)
    print("🔍 RUNNING CHECKPOINT: VENDOR ECHO")
    print("="*40)
    
    payload = {
        "request_id": "startup_check", 
        "query": "STATUS_CHECK"
    }
    
    for attempt in range(retries):
        try:
            response = requests.post("http://localhost:8001/a2a/echo", json=payload, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ PASSED: VendorBot replied: '{data['message']}'")
                print(f"   (Internal Truth: {data.get('internal_truth_is_healthy', 'Unknown')})")
                return True
            else:
                print(f"⚠️  Attempt {attempt+1}/{retries} Failed: Status {response.status_code}")
                print(f"    Response Body: {response.text}")
                time.sleep(1) # Wait before retry
                
        except Exception as e:
            print(f"⚠️  Attempt {attempt+1}/{retries} Connection Error: {e}")
            time.sleep(1)

    print(f"❌ FAILED: VendorBot did not respond successfully after {retries} attempts.")
    print(f"   Details: {e}")
    return False

if __name__ == "__main__":
    print("🚀 Initializing D.A.R.T. Simulation Environment...")
    
    # 1. Start VendorBot (Port 8001)
    p_vendor = multiprocessing.Process(target=run_vendor_server)
    p_vendor.start()
    
    # 2. Start MCP Server (Port 8000)
    p_mcp = multiprocessing.Process(target=run_mcp_server)
    p_mcp.start()

    # 3. Health Checks
    print("\n[Health Checks]")
    vendor_ready = wait_for_port(8001, "VendorBot")
    mcp_ready = wait_for_port(8000, "MockEnterprise")

    if vendor_ready and mcp_ready:
        # 4. Run the detailed checkpoint verification (Now Robust)
        if verify_vendor_echo():
            print("\n" + "="*40)
            print("🌍 WORLD BUILT SUCCESSFULLY")
            print("="*40)
            print("   - Mock Enterprise: http://localhost:8000/sse")
            print("   - Vendor Bot:      http://localhost:8001/docs")
            print("\nPress Ctrl+C to stop the simulation.")
            
            try:
                p_vendor.join()
                p_mcp.join()
            except KeyboardInterrupt:
                print("\n🛑 Shutting down simulation...")
                p_vendor.terminate()
                p_mcp.terminate()
                sys.exit(0)
        else:
            print("\n❌ CRITICAL ERROR: World Checkpoint Failed.")
            p_vendor.terminate()
            p_mcp.terminate()
            sys.exit(1)
    else:
        print("\n❌ CRITICAL ERROR: Servers failed to start.")
        p_vendor.terminate()
        p_mcp.terminate()
        sys.exit(1)
