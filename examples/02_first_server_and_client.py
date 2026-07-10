"""
examples/02_first_server_and_client.py — the raw SDK, once (offline, no key).
=============================================================================

Example 01 showed the JSON messages; here we send real ones, using the official
SDK's client API with NO wrapper, so you see the actual ceremony exactly as the
SDK docs describe it. This is the only example that uses the raw API directly —
after this we use the small `MCPClient` wrapper to keep the lessons uncluttered.

What happens:
  1. We describe how to launch the server (servers/calculator.py) over stdio.
  2. `stdio_client(...)` spawns it as a subprocess and gives us a read/write
     pair (the pipe).
  3. `ClientSession(read, write)` speaks the protocol over that pipe.
  4. `await session.initialize()` runs the handshake.
  5. `list_tools()` and `call_tool(...)` are the `tools/list` / `tools/call`
     methods from example 01.

A server and a client talking — and not a single token of LLM involved. This is
the free, offline foundation everything else builds on.

SDK note: targets the official `mcp` Python SDK 1.x.
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters  # type: ignore[import-untyped]
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

    # Two nested context managers: the transport (subprocess + pipe), then the
    # session (the protocol on top of the pipe). This is the canonical shape.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1) Handshake — always first.
            init = await session.initialize()
            print(f"connected to server: {init.serverInfo.name} "
                  f"(protocol {init.protocolVersion})")

            # 2) Discover tools (tools/list).
            tools = await session.list_tools()
            print(f"\nserver advertises {len(tools.tools)} tool(s):")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0] if t.description else ''}")
                print(f"    inputSchema: {t.inputSchema}")

            # 3) Call the tool (tools/call). A model would *request* this; here
            #    we (the client) just do it directly.
            result = await session.call_tool("calculator", {"expression": "23 * 47"})
            text = "".join(getattr(b, "text", "") for b in result.content)
            print(f"\ncall calculator(expression='23 * 47') -> {text}")
            print(f"isError: {result.isError}")


if __name__ == "__main__":
    asyncio.run(main())
