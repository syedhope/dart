# ==============================================================================
# File Location: dart-agent/src/utils/config.py
# File Name: config.py
# Description:
# - Central configuration for API keys, model settings, paths, and scenario state.
# - Resolves writable paths, persists active scenario selection, and loads YAML scenarios.
# Inputs:
# - Environment variables (API keys, memory dir, scenario override); filesystem state.
# Outputs:
# - Config object with model/paths/ports; loaded scenario data; persisted scenario flags.
# ==============================================================================

import os
import yaml
import glob
import tempfile
from typing import Dict, Any, List

class DartConfig:
    def __init__(self):
        # --- 1. LLM Settings ---
        # Priority: Env Var > Default
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        
        # We centralize the model name here. 
        # Future UI can update this attribute at runtime.
        self.model_name = "gemini-2.5-flash-lite" 
        self.temperature = 0.0
        self.max_tokens = 1024

        # --- 2. Paths & Directories ---
        self.project_root = os.getcwd()
        self.scenarios_dir = os.path.join(self.project_root, "scenarios")
        self.logs_dir = os.path.join(self.project_root, "logs")
        self.memory_db_path = self._resolve_memory_path()
        self.active_scenario_state_path = os.path.join(self.project_root, ".dart_active_scenario")
        self.scenario_state_path = os.path.join(self.project_root, ".dart_scenarios_state")
        self._scenario_state_cache = self._load_scenario_state()
        self.google_custom_search_key = os.getenv("GOOGLE_CUSTOM_SEARCH_KEY")
        self.google_cx_id = os.getenv("GOOGLE_CUSTOM_SEARCH_CX")

        # --- 3. Simulation Defaults ---
        # Default scenario if none is specified in Env
        self.default_scenario = "01_drift.yaml" 
        
        # --- 4. Server Settings (Ports) ---
        # Centralizing ports makes it easier to run dev/prod environments later
        self.mcp_server_port = 8000
        self.vendor_port = 8001
        self.mcp_server_url = f"http://localhost:{self.mcp_server_port}/sse"
        self.vendor_api_url = f"http://localhost:{self.vendor_port}"

        # --- 5. Feature Flags ---
        # Set to False to run backend logic without Chainlit updates
        self.enable_ui_streaming = True

    def _resolve_memory_path(self) -> str:
        env_path = os.getenv("DART_MEMORY_DIR")
        candidates = []
        if env_path:
            candidates.append(env_path)
        # Prefer system temp to avoid read-only sync folders
        candidates.append(os.path.join(tempfile.gettempdir(), "dart_memory_store"))
        candidates.append(os.path.join(self.project_root, "dart_memory_store"))

        for candidate in candidates:
            try:
                os.makedirs(candidate, exist_ok=True)
                sentinel = os.path.join(candidate, ".write_test")
                with open(sentinel, "w") as f:
                    f.write("ok")
                os.remove(sentinel)
                if env_path and candidate == env_path:
                    print(f"ℹ️ Memory store path set from DART_MEMORY_DIR: {candidate}")
                elif candidate.startswith(tempfile.gettempdir()):
                    print(f"ℹ️ Using temp memory store: {candidate}")
                return candidate
            except Exception as e:
                print(f"⚠️ Memory store path not writable ({candidate}): {e}")

        # Final fallback: temp dir without checks
        fallback = os.path.join(tempfile.gettempdir(), "dart_memory_store")
        os.makedirs(fallback, exist_ok=True)
        return fallback

    def _read_persisted_scenario(self) -> str:
        if not os.path.exists(self.active_scenario_state_path):
            return ""
        try:
            with open(self.active_scenario_state_path, "r") as f:
                persisted = f.read().strip()
            return persisted
        except Exception as e:
            print(f"⚠️ Config Warning: Failed to read active scenario cache: {e}")
            return ""

    def persist_active_scenario(self, scenario_path: str):
        """Persists the selected scenario path so other processes (MCP/Servers) can stay in sync."""
        try:
            with open(self.active_scenario_state_path, "w") as f:
                f.write(scenario_path.strip())
        except Exception as e:
            print(f"⚠️ Config Warning: Failed to persist scenario {scenario_path}: {e}")

    def _load_scenario_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.scenario_state_path):
            return {}
        try:
            with open(self.scenario_state_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ Config Warning: Failed to read scenario state: {e}")
            return {}

    def _save_scenario_state(self):
        try:
            with open(self.scenario_state_path, "w") as f:
                yaml.safe_dump(self._scenario_state_cache, f)
        except Exception as e:
            print(f"⚠️ Config Warning: Failed to persist scenario state: {e}")

    def get_scenario_flag(self, scenario_id: str, key: str, default=False):
        return self._scenario_state_cache.get(scenario_id, {}).get(key, default)

    def set_scenario_flag(self, scenario_id: str, key: str, value: bool):
        state = self._scenario_state_cache.setdefault(scenario_id, {})
        state[key] = value
        self._save_scenario_state()

    def get_active_scenario_path(self) -> str:
        """Determines which YAML file to load."""
        # 1. Check Env Var (Used by demo scripts/CLI)
        env_scenario = os.getenv("DART_SCENARIO")
        if env_scenario:
            return env_scenario

        # 2. Check persisted selection (shared across processes)
        persisted = self._read_persisted_scenario()
        if persisted and os.path.exists(persisted):
            return persisted
        
        # 3. Return Default
        return os.path.join(self.scenarios_dir, self.default_scenario)

    def load_active_scenario(self) -> Dict[str, Any]:
        """Loads the actual YAML content."""
        path = self.get_active_scenario_path()
        if not os.path.exists(path):
            # Fallback for safety
            print(f"⚠️ Config Warning: Scenario {path} not found. Falling back to default.")
            path = os.path.join(self.scenarios_dir, self.default_scenario)
            
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return data
        except Exception as e:
            print(f"❌ Config Error: Failed to load scenario: {e}")
            return {}

    def list_available_scenarios(self) -> List[str]:
        """
        Helper for UI: Returns a list of available scenario filenames.
        Usage: Dropdown menu in React App.
        """
        if not os.path.exists(self.scenarios_dir):
            return []
        files = glob.glob(os.path.join(self.scenarios_dir, "*.yaml"))
        return [os.path.basename(f) for f in files]

# Global Singleton
config = DartConfig()

def get_active_scenario() -> Dict[str, Any]:
    """Helper for modules that need the latest scenario data on-demand."""
    return config.load_active_scenario()

# [BACKWARD COMPATIBILITY] 
# Existing code can still import ACTIVE_SCENARIO, but prefer get_active_scenario().
ACTIVE_SCENARIO = get_active_scenario()
