# ==============================================================================
# File Location: dart-agent/src/ui/bridge.py
# File Name: bridge.py
# Description:
# - Bridges trace logging to Chainlit UI (log, thought, table) without method swizzling.
# - Mirrors console traces into chat with formatting and gating via config.
# Inputs:
# - Trace logger calls (source/message/level), optional incident_id; config flag for UI streaming.
# Outputs:
# - Original trace log invocation; mirrored Chainlit messages/tables when streaming is enabled.
# ==============================================================================

import chainlit as cl
import pandas as pd
from src.utils.trace_viz import trace as original_trace
from src.utils.config import config

# Keep references to the ORIGINAL bound methods
_original_log = original_trace.log
_original_agent_thought = original_trace.agent_thought
_original_show_table = original_trace.show_table


def _format_content(source: str, message: str, level: str) -> str:
    """
    Format a log/thought into a nice markdown message for Chainlit.
    """
    content = (message or "").strip()
    prefix = f"**{source}:** "

    if level == "thought":
        content = f"💭 *{content}*"
    elif level == "error":
        content = f"🚨 **{content}**"
    elif level == "success":
        content = f"✅ **{content}**"
    elif level == "warning":
        content = f"⚠️ **{content}**"

    if "\n" in content:
        content = content.replace("\n", "\n\n")

    return prefix + content


def log_wrapper(
    source: str,
    message: str,
    level: str = "info",
    incident_id: str | None = None,
    **kwargs,
):
    """
    Replacement for trace.log that:
      1) Calls the original logger (console/file/etc).
      2) Mirrors the message into the Chainlit UI if enabled.
    NOTE: This is a plain function, not a method. 'self' is NOT involved anymore.
    """
    # --- 1. Call the original TraceLogger.log -------------------------------
    try:
        # Most common case: original signature: (source, message, level="info", incident_id=None, ...)
        _original_log(source, message, level=level, incident_id=incident_id, **kwargs)
    except TypeError:
        # Fallback if original_log doesn't accept incident_id/kwargs
        _original_log(source, message, level)

    # --- 2. Emit to Chainlit UI (if enabled) --------------------------------
    if not getattr(config, "enable_ui_streaming", False):
        return

    try:
        final_content = _format_content(source, message, level)
        cl.run_sync(
            cl.Message(
                content=final_content,
                author=source,
            ).send()
        )
    except Exception as e:
        print(f"⚠️ UI Bridge Error in log_wrapper: {e}")


def agent_thought_wrapper(
    agent_name: str,
    thought: str,
    incident_id: str | None = None,
    **kwargs,
):
    """
    Replacement for trace.agent_thought that:
      1) Calls the original implementation.
      2) Mirrors the thought as a 'thought' message in Chainlit.
    """
    # --- 1. Call the original TraceLogger.agent_thought ---------------------
    try:
        _original_agent_thought(
            agent_name,
            thought,
            incident_id=incident_id,
            **kwargs,
        )
    except TypeError:
        # Fallback if original doesn't accept incident_id/kwargs
        _original_agent_thought(agent_name, thought)

    # --- 2. Emit to Chainlit UI (if enabled) --------------------------------
    if not getattr(config, "enable_ui_streaming", False):
        return

    try:
        final_content = _format_content(agent_name, thought, "thought")
        cl.run_sync(
            cl.Message(
                content=final_content,
                author=agent_name,
            ).send()
        )
    except Exception as e:
        print(f"⚠️ UI Bridge Error in agent_thought_wrapper: {e}")


def activate_bridge():
    """
    Install the wrappers on the global TraceLogger instance.

    IMPORTANT:
      - We assign plain functions to the INSTANCE (original_trace),
        so Python does NOT try to inject 'self', avoiding all
        bound/unbound method weirdness.
    """
    print("🌉 UI Bridge: Installing UI wrappers for TraceLogger...")

    # Replace instance attributes with our wrapper functions.
    # After this, everywhere in the code that calls `trace.log(...)`
    # or `trace.agent_thought(...)` will hit our wrappers.
    original_trace.log = log_wrapper
    original_trace.agent_thought = agent_thought_wrapper
    original_trace.show_table = show_table_wrapper


def show_table_wrapper(title: str, data):
    """
    Mirrors TraceLogger.show_table into the Chainlit UI as a dataframe element.
    """
    try:
        _original_show_table(title, data)
    except TypeError:
        _original_show_table(title, [])

    if not getattr(config, "enable_ui_streaming", False):
        return

    try:
        if not data:
            cl.run_sync(
                cl.Message(
                    content=f"📊 **{title}**\n_No rows to display._"
                ).send()
            )
            return

        df = pd.DataFrame(data)
        cl.run_sync(
            cl.Message(
                content=f"📊 **{title}**",
                elements=[
                    cl.Dataframe(
                        name=f"{title}_table",
                        data=df,
                        display="inline"
                    )
                ]
            ).send()
        )
    except Exception as e:
        print(f"⚠️ UI Bridge Error in show_table_wrapper: {e}")
