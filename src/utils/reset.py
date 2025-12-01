# ==============================================================================
# File Location: dart-agent/src/utils/reset.py
# File Name: reset.py
# Description:
# - Utility to wipe vector memory (Chroma) and session logs for a clean slate.
# Inputs:
# - None (operates on local paths configured in constants).
# Outputs:
# - Side effects on filesystem: removed memory store and cleared logs; console logs.
# ==============================================================================

import shutil
import os
import sys
import glob
import pathlib
import subprocess
import signal
import time

# Must match DB_PATH in src/memory/brain.py
DB_PATH = "dart_memory_store"
LOG_DIR = "logs"
SCENARIOS_DIR = "scenarios"
SCENARIOS_BASELINE_DIR = "scenarios_baseline"
DEFAULT_PORTS = [8000, 8001]
SCENARIO_FILES = [
    "01_drift.yaml",
    "02_hard_mode.yaml",
    "03_gitops.yaml",
    "04_ingestion_deadlock.yaml",
    "05_vendor_deadlock.yaml",
    "06_context_storm.yaml",
    "07_observability_guard.yaml",
    "08_snowflake_google.yaml",
    "09_kb_lookup.yaml",
]

def _kill_processes_on_ports(ports):
    """
    Attempts to kill any process listening on the given ports.
    Uses lsof; if unavailable, logs a warning.
    """
    for port in ports:
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
            pids = [int(p) for p in result.stdout.strip().splitlines() if p.strip()]
            if not pids:
                print(f"   ✅ No process found on port {port}.")
                continue
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"   ✅ Killed PID {pid} on port {port}.")
                except Exception as e:
                    print(f"   ⚠️ Failed to kill PID {pid} on port {port}: {e}")
        except FileNotFoundError:
            print("   ⚠️ lsof not available; cannot auto-kill ports.")
            return

def _wait_for_ports_free(ports, retries=5, delay=1.0):
    """
    After killing, ensure ports are free before restart.
    """
    for attempt in range(retries):
        busy = []
        try:
            for port in ports:
                result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
                pids = [p for p in result.stdout.strip().splitlines() if p.strip()]
                if pids:
                    busy.append((port, pids))
        except FileNotFoundError:
            return  # lsof missing; nothing we can do
        if not busy:
            return
        time.sleep(delay)
    if busy:
        print(f"   ⚠️ Ports still busy after retries: {busy}")

def _restart_mcp_servers():
    """
    Relaunches the MCP + Vendor servers via startup.py in the background.
    """
    try:
        subprocess.Popen(
            [sys.executable, "-m", "src.servers.startup"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("   ✅ Restarted MCP/Vendor servers in background (startup.py).")
    except Exception as e:
        print(f"   ⚠️ Failed to restart MCP/Vendor servers: {e}")

def reset_environment():
    print("🧹 Cleaning D.A.R.T. Environment...")
    print("   🔪 Terminating any servers on ports 8000/8001...")
    _kill_processes_on_ports(DEFAULT_PORTS)
    _wait_for_ports_free(DEFAULT_PORTS)
    
    # 1. Wipe Vector Memory (The Brain)
    if os.path.exists(DB_PATH):
        try:
            shutil.rmtree(DB_PATH)
            print(f"   ✅ Memory Store ({DB_PATH}) wiped.")
        except Exception as e:
            print(f"   ❌ Failed to wipe memory: {e}")
    else:
        print("   ✅ Memory Store was already clean.")

    # 2. Wipe Session Logs (The History)
    if os.path.exists(LOG_DIR):
        try:
            # We delete the files but keep the folder
            for filename in os.listdir(LOG_DIR):
                file_path = os.path.join(LOG_DIR, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
            print(f"   ✅ Session Logs ({LOG_DIR}/) cleared.")
        except Exception as e:
            print(f"   ⚠️ Failed to clean logs: {e}")

    # 3. Restore mutable scenarios from baseline (if missing in baseline, seed from current scenarios)
    baseline_root = pathlib.Path(SCENARIOS_BASELINE_DIR)
    target_root = pathlib.Path(SCENARIOS_DIR)
    if baseline_root.exists():
        try:
            baseline_root.mkdir(parents=True, exist_ok=True)
            target_root.mkdir(parents=True, exist_ok=True)
            for scenario_file in SCENARIO_FILES:
                src = baseline_root / scenario_file
                dst = target_root / scenario_file
                # If baseline missing but current scenario exists, seed baseline from current
                if (not src.exists()) and dst.exists():
                    shutil.copy(dst, src)
                if src.exists():
                    shutil.copy(src, dst)
            print("   ✅ Scenarios restored from baseline.")
        except Exception as e:
            print(f"   ⚠️ Failed to restore scenarios: {e}")

    # 3. Clear __pycache__ (Good hygiene)
    # Using python implementation instead of shell for cross-platform safety
    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(root, "__pycache__"))
            dirs.remove("__pycache__") # Don't visit into it
    print("   ✅ PyCache cleared.")
    
    print("   🔄 Restarting MCP/Vendor servers...")
    _restart_mcp_servers()
    
    print("\n✨ Environment is pristine. Ready for 'Run 1' (Learning Mode).")
    print("   (Servers relaunched via src.servers.startup in background.)")

if __name__ == "__main__":
    reset_environment() 
