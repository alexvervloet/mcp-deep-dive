"""
examples/03_client_calls_tool.py — the FREE-first runnable (offline, no key).
=============================================================================

Same idea as example 02 — a client lists and calls a tool on a server — but now
through the small `MCPClient` wrapper from `client/mcp_client.py`. Compare the
two files: the wrapper hides the async ceremony so the *protocol* steps stand
out (connect -> list -> call), which is what matters.

This is the example to really sit with. It proves the core claim of the whole
repo: **you write a server once, and any MCP-speaking client can discover and
use its tools — with no LLM anywhere.** Everything later (resources, prompts, a
real toolbox, an LLM host) is a small addition to exactly this.

Run it — it costs nothing and needs no key:

    python examples/03_client_calls_tool.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.mcp_client import MCPClient, run


async def main():
    # Launch the calculator server and connect. The `async with` runs the
    # handshake on entry and shuts the subprocess down cleanly on exit.
    async with MCPClient("servers/calculator.py") as client:

        # 1) DISCOVER: what does this server offer? (tools/list)
        tools = await client.list_tools()
        print("tools the server advertises:")
        for t in tools:
            print(f"  - {t.name}: {t.description.splitlines()[0]}")

        # 2) CALL: run a tool by name with arguments. (tools/call)
        print("\ncalling the tool over the protocol:")
        for expr in ["2 + 2", "23 * 47", "2 ** 10"]:
            out = await client.call_tool("calculator", {"expression": expr})
            print(f"  calculator({expr!r}) -> {out}")

        # 3) Errors come back IN-BAND, not as a crash — the server catches the
        #    exception and marks the result isError; our wrapper prefixes it.
        print("\na bad expression returns an error result, not a crash:")
        out = await client.call_tool("calculator", {"expression": "2 +"})
        print(f"  calculator('2 +') -> {out}")


if __name__ == "__main__":
    run(main())
