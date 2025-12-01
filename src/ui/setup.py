# ==============================================================================
# File Location: dart-agent/src/ui/setup.py
# File Name: setup.py
# Description:
# - Sets up static Chainlit UI: avatars, roster, readiness board, and mission buttons.
# - Downloads avatars on demand and posts roster/readiness messages.
# Inputs:
# - None required; uses network to fetch avatars; random latency for readiness display.
# Outputs:
# - Chainlit messages and actions to drive mission selection UI.
# ==============================================================================

import chainlit as cl
import random
import os
import httpx

# --- 1. Avatar Configuration ---
async def setup_avatars():
    """Downloads robot avatars from DiceBear."""
    avatar_dir = "public/avatars"
    if not os.path.exists(avatar_dir):
        os.makedirs(avatar_dir, exist_ok=True)

    base_url = "https://api.dicebear.com/9.x/bottts-neutral/svg?seed="
    agents = ["Syx", "Neon", "Kai", "Shield", "Echo", "System"]
    
    for agent in agents:
        file_path = f"{avatar_dir}/{agent}.svg"
        if not os.path.exists(file_path):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{base_url}{agent}")
                    if response.status_code == 200:
                        with open(file_path, "wb") as f:
                            f.write(response.content)
            except Exception as e:
                print(f"⚠️ Failed to download avatar for {agent}: {e}")

# --- 2. The Active Roster (In-Chat) ---
async def setup_roster():
    """
    Renders the Agent Team Roster directly in the chat so it's impossible to miss.
    Replaces the hidden 'chainlit.md' sidebar.
    """
    roster_content = """
    ### 👥 ACTIVE AGENT ROSTER
    
    | AGENT | ROLE | CAPABILITY |
    | :--- | :--- | :--- |
    | **Syx** | 🔵 Commander | Strategy & Memory |
    | **Neon** | 🟡 Auditor | Forensics & Analysis |
    | **Kai** | 🟣 Engineer | SQL & GitOps |
    | **Shield** | 🔴 Safety | Policy & Authorization |
    """
    await cl.Message(content=roster_content, author="System").send()

# --- 3. The Lobby & Readiness Board ---
async def setup_lobby():
    """
    Simulates boot-up and renders Mission Buttons.
    """
    latency_swarm = random.randint(12, 45)
    
    readiness_md = f"""
    ### 🖥️ SYSTEM READINESS CHECK
    
    | SUBSYSTEM | STATUS | LATENCY |
    | :--- | :---: | :---: |
    | **Brain (Gemini-1.5)** | 🟢 READY | 240ms |
    | **Swarm (Agents)** | 🟢 READY | {latency_swarm}ms |
    | **Memory (ChromaDB)** | 🟢 READY | 15ms |
    | **Vendor Uplink** | 🟡 LAG | 120ms |
    
    *System initialized. Select a mission profile below.*
    """
    
    await cl.Message(content=readiness_md, author="System").send()
    
    # [RESTORED] Mission Buttons
    actions = [
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
        cl.Action(
            name="mission_selector", 
            value="obs", 
            label="🛰️ Mission: Observability Guard", 
            description="Scenario 7: Detection catches silent failure",
            payload={"scenario": "obs"}
        ),
        cl.Action(
            name="mission_selector", 
            value="google", 
            label="🌐 Mission: Snowflake SOS", 
            description="Scenario 8: Google lookup demo",
            payload={"scenario": "google"}
        ),
    ]
    
    await cl.Message(content="**SELECT MISSION PROFILE:**", actions=actions).send()
