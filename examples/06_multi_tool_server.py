"""
examples/06_multi_tool_server.py — a real, many-tool server (offline, no key).
==============================================================================

So far one tool at a time. Real servers expose a handful of related tools, and
the client discovers them all the same way. This connects to servers/toolbox.py
— calculator, search_notes, word_count, save_note, plus its resources and a
prompt — and exercises several tools over one connection.

Two things to notice:

  - You didn't change the CLIENT to get new tools. The server grew; `tools/list`
    just returns more. That's the protocol paying off: capability lives in the
    server, and any host gets it for free.

  - `save_note` has a SIDE EFFECT (it writes a file). Over MCP that's just
    another tool call — which is exactly why the security section and the
    capstone add a human-approval gate around side-effecting tools. Here we call
    it directly to see it work; you'll see it land in ./workspace/.

Run it (offline, no key):

    python examples/06_multi_tool_server.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.mcp_client import MCPClient, run


async def main():
    async with MCPClient("servers/toolbox.py") as client:

        tools = await client.list_tools()
        print(f"the toolbox server advertises {len(tools)} tools:")
        for t in tools:
            print(f"  - {t.name}: {t.description.splitlines()[0]}")

        print("\nrouting a few calls to different tools:")
        print("  calculator('19 * 12')   ->", await client.call_tool(
            "calculator", {"expression": "19 * 12"}))
        print("  search_notes('offline') ->", (await client.call_tool(
            "search_notes", {"query": "offline editing"})).replace("\n", " | "))
        print("  word_count('a b c d')   ->", await client.call_tool(
            "word_count", {"text": "the quick brown fox jumps"}))

        # The side-effecting tool. (No approval gate here — that's the capstone's
        # job. We're just showing it's a normal tool call over the protocol.)
        print("\ncalling the side-effecting tool (writes a file):")
        print("  save_note(...) ->", await client.call_tool(
            "save_note", {"title": "mcp demo", "body": "written over MCP, no LLM"}))
        print("  (check ./workspace/mcp_demo.md)")


if __name__ == "__main__":
    run(main())
