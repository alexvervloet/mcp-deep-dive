"""
examples/02_first_server_and_client.py: the raw SDK, once (offline, no key).

Example 01 showed the JSON messages; here we send real ones, using the official
SDK's client API with NO wrapper, so you see the actual ceremony exactly as the
SDK docs describe it. This is the only example that uses the raw API directly 
after this we use the small `MCPClient` wrapper to keep the lessons uncluttered.

What happens:
  1. We describe how to launch the server (servers/calculator.py) over stdio.
  2. `stdio_client(...)` describes the subprocess transport (the pipe).
  3. `Client(...)` opens it and selects modern MCP 2026-07-28 automatically.
     It may probe optional `server/discover`; there is no initialize handshake.
  4. `list_tools()` and `call_tool(...)` are the `tools/list` / `tools/call`
     methods from example 01.

A server and a client talking, and not a single token of LLM involved. This is
the free, offline foundation everything else builds on.

SDK note: targets the official `mcp` Python SDK 2.x.
"""

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters  # type: ignore[import-untyped]
from mcp.client.stdio import stdio_client  # type: ignore[import-untyped]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main():
    # How to start the server: run it with THIS interpreter so it sees the same
    # venv (and the installed mcp SDK).
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(REPO_ROOT, "servers", "calculator.py")],
        env=os.environ.copy(),
    )

    # Client owns the transport lifecycle. Its default mode probes modern
    # `server/discover`, then falls back to initialize only for a legacy server.
    async with Client(stdio_client(params)) as client:
        print(f"connected (protocol {client.protocol_version})")

        # 1) Discover tools (tools/list).
        tools = await client.list_tools()
        print(f"\nserver advertises {len(tools.tools)} tool(s):")
        for t in tools.tools:
            print(f"  - {t.name}: {t.description.splitlines()[0] if t.description else ''}")
            print(f"    input_schema: {t.input_schema}")

        # 2) Call the tool (tools/call). A model would *request* this; here
        #    we (the client) just do it directly.
        result = await client.call_tool("calculator", {"expression": "23 * 47"})
        text = "".join(getattr(b, "text", "") for b in result.content)
        print(f"\ncall calculator(expression='23 * 47') -> {text}")
        print(f"is_error: {result.is_error}")


if __name__ == "__main__":
    asyncio.run(main())
