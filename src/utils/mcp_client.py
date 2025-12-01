# ==============================================================================
# File Location: dart-agent/src/utils/mcp_client.py
# File Name: mcp_client.py
# Description:
# - Lightweight MCP client to call tools over SSE with retries.
# - Extracts JSON/text payloads from MCP responses for agent use.
# Inputs:
# - Tool name and arguments; MCP server URL from config.
# Outputs:
# - Parsed MCP tool results (JSON or text) or None on failure; trace logs/prints.
# ==============================================================================

import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from src.utils.trace_viz import trace
from src.utils.config import config
from typing import Any, Dict

class SimpleMCPClient:
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = {}, retries: int = 3) -> Any:
        """
        Asynchronous tool execution. Used by Agents (Neon, Kai).
        FIXED: Properly extract JSON/data from MCP response instead of `.text`.
        """
        last_error = None
        
        for attempt in range(retries):
            try:
                async with sse_client(config.mcp_server_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)

                        print("\n🟥 RAW RESULT FROM MCP SERVER →", result)
                        print("🟥 RAW CONTENT FIELD →", getattr(result, "content", None), "\n")

                        if result and result.content:
                            item = result.content[0]

                            # JSON content
                            if hasattr(item, "data") and item.data is not None:
                                print("🟩 RETURNING JSON →", item.data)
                                return item.data

                            # Text content
                            if hasattr(item, "text") and item.text is not None:
                                print("🟩 RETURNING TEXT →", item.text)
                                return item.text

                            print("🟨 RETURNING RAW ITEM →", item)
                            return item

                        print("🟥 RESULT HAD NO CONTENT → returning fallback message.\n")
                        return "Success (No output)"

            except Exception as e:
                last_error = e
                wait_time = 1.0 * (attempt + 1)
                await asyncio.sleep(wait_time)

        trace.log("MCP_Client", f"Failed to call {tool_name} after {retries} attempts: {last_error}", "error")
        return f"Error: {last_error}"

# Global Singleton
mcp_wrapper = SimpleMCPClient()
