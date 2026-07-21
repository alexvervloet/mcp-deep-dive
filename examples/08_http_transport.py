"""
examples/08_http_transport.py: connect to a server over HTTP (offline, no key).

The stdio examples launched the server themselves. An HTTP server is different:
it's already running somewhere, and you connect to it by URL. This example talks
to servers/calculator_http.py over streamable HTTP: same tools, same
`tools/list` / `tools/call`, just a network transport underneath.

TWO TERMINALS for this one:

  terminal 1:  python servers/calculator_http.py
               (starts the service on http://127.0.0.1:8000/mcp and stays up)

  terminal 2:  python examples/08_http_transport.py

Still no LLM and no key; it's just the client/server demo over a different
pipe. Notice what changed and what didn't:
  - CHANGED: we use `streamablehttp_client(url)` instead of `stdio_client(...)`,
    and we point at a URL instead of launching a subprocess.
  - UNCHANGED: `ClientSession`, `initialize()`, `list_tools()`, `call_tool()` 
    once the session exists, the transport is invisible.

SDK note: targets the official `mcp` Python SDK 1.x. In 1.x the streamable-HTTP
client is `streamablehttp_client` (no underscores) and yields a THREE-tuple
(read, write, get_session_id); the third item is an HTTP-only session-id getter
we don't need here. (A newer 2.x SDK renames this; this repo targets 1.x.)
"""

import asyncio

from mcp import ClientSession  # type: ignore[import-untyped]
from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-untyped]

URL = "http://127.0.0.1:8000/mcp"


async def main():
    print(f"connecting to {URL} ...")
    try:
        async with streamablehttp_client(URL) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"connected to: {init.serverInfo.name}")

                tools = await session.list_tools()
                print(f"tools: {[t.name for t in tools.tools]}")

                result = await session.call_tool("calculator", {"expression": "111 * 3"})
                text = "".join(getattr(b, "text", "") for b in result.content)
                print(f"calculator('111 * 3') -> {text}")
    except Exception as exc:  # almost always: the server isn't running yet
        print(f"\ncould not connect ({exc!r}).")
        print("Start the server first, in another terminal:")
        print("    python servers/calculator_http.py")


if __name__ == "__main__":
    asyncio.run(main())
