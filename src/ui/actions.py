# ==============================================================================
# File Location: dart-agent/src/ui/actions.py
# File Name: actions.py
# Description:
# - Human-in-the-loop approval UI helpers for Chainlit.
# - Normalizes action payloads and falls back to CLI prompt when needed.
# Inputs:
# - Plan/reason strings from Shield; user action responses via Chainlit or stdin.
# Outputs:
# - Chainlit messages for approval/block; boolean approval result to callers.
# ==============================================================================

import chainlit as cl

def _extract_action_value(response):
    if response is None:
        return None
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if "value" in response:
            return response["value"]
        payload = response.get("payload")
        if isinstance(payload, dict):
            return payload.get("value")
    payload = getattr(response, "payload", None)
    if isinstance(payload, dict):
        return payload.get("value")
    value = getattr(response, "value", None)
    if isinstance(value, str):
        return value
    name = getattr(response, "name", None)
    if isinstance(name, str) and name in {"approve", "reject"}:
        return name
    return None

async def request_approval_ui(plan: str, reason: str) -> bool:
    res = await cl.AskActionMessage(
        content=f"🛑 **SECURITY ALERT: {reason}**\n\nThe agent wants to execute:\n`{plan}`",
        actions=[
            cl.Action(name="approve", payload={"value": "approve"}, label="✅ AUTHORIZE", description="Allow this action"),
            cl.Action(name="reject", payload={"value": "reject"}, label="⛔ BLOCK", description="Stop this action")
        ],
        timeout=600
    ).send()

    decision = _extract_action_value(res)
    if decision not in {"approve", "reject"}:
        try:
            fallback = input(f"[Shield] {reason}\nAuthorize '{plan}'? (y/n): ")
            decision = "approve" if fallback.strip().lower().startswith("y") else "reject"
        except EOFError:
            decision = "reject"

    if decision == "approve":
        await cl.Message(content="✅ **User Authorized Action.**").send()
        return True

    await cl.Message(content="⛔ **User Blocked Action.**").send()
    return False
