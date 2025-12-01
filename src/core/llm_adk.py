# ==============================================================================
# File Location: dart-agent/src/core/llm_adk.py
# Description:
# - ADK-based Gemini helpers (Neon, Kai) with per-call Runner + SessionService.
# - Avoids cross-thread loops by creating Runner/Session per invocation.
# Inputs:
# - Prompts/personas for agents; Google API key from env; model config from config.py.
# Outputs:
# - LLM-generated text responses via ADK runner.
# ==============================================================================

import asyncio
import os
from typing import List
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from src.utils.config import config


def _make_gemini_model():
    return Gemini(
        model=config.model_name,
        api_key=config.google_api_key,
    )


async def _run_agent(prompt: str, agent: Agent, app_name: str, user_id: str, session_id: str) -> str:
    # Ensure GOOGLE_API_KEY is visible to genai
    if config.google_api_key:
        os.environ["GOOGLE_API_KEY"] = config.google_api_key

    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    # Create or get session
    try:
        session = await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    except Exception:
        session = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)

    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events: List[types.Content] = []
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
        events.append(event)
    return _extract_text(events)


def call_neon(prompt: str) -> str:
    """
    Synchronous helper for Neon agent using ADK in the current loop.
    """
    agent = Agent(
        name="Neon",
        model=_make_gemini_model(),
        tools=[google_search],
        description="Neon the forensic auditor: correlate logs/schema/data/vendor signals to produce concise root cause.",
        instruction=(
            "Respond with:\n"
            "- Root Cause: <one-line>\n"
            "- Evidence: <bullets of key signals>\n"
            "- Recommendation: <next step>"
        ),
    )
    try:
        return asyncio.run(_run_agent(prompt, agent, app_name="dart-neon", user_id="adk-user", session_id="adk-neon"))
    except RuntimeError:
        # If we're already in an event loop, create a new task and wait
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_run_agent(prompt, agent, app_name="dart-neon", user_id="adk-user", session_id="adk-neon"))


def call_kai(prompt: str) -> str:
    """
    Synchronous helper for Kai agent using ADK in the current loop.
    """
    agent = Agent(
        name="Kai",
        model=_make_gemini_model(),
        tools=[google_search],
        description="Kai the remediation engineer: choose minimal, safe fixes (SQL/Git) aligned to the diagnosis.",
        instruction=(
            "For SQL: single Snowflake command, no comments. Prefer ALTER ADD or targeted updates.\n"
            "For Git: return only the fixed code block. No prose."
        ),
    )
    try:
        return asyncio.run(_run_agent(prompt, agent, app_name="dart-kai", user_id="adk-user", session_id="adk-kai"))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_run_agent(prompt, agent, app_name="dart-kai", user_id="adk-user", session_id="adk-kai"))


def _extract_text(events_list):
    if not events_list:
        return ""
    last = events_list[-1]
    if hasattr(last, "content") and last.content and getattr(last.content, "parts", None):
        parts = []
        for p in last.content.parts:
            text = getattr(p, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return str(last)
