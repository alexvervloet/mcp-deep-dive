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
  - CHANGED: we use `streamable_http_client(url)` instead of `stdio_client(...)`,
    and we point at a URL instead of launching a subprocess.
  - UNCHANGED: `ClientSession`, `initialize()`, `list_tools()`, `call_tool()`
    once the session exists, the transport is invisible.

SDK note: targets the official `mcp` Python SDK 2.x, where the streamable-HTTP
client is `streamable_http_client` and yields a TWO-tuple (read, write), the
same shape `stdio_client` yields. That is the point of the section: both
transports hand you the same pair, so `ClientSession` cannot tell them apart.

If you are following a 1.x tutorial it will call this `streamablehttp_client`
(no underscores) and unpack a THREE-tuple, the third item being an HTTP-only
session-id getter that 2.x dropped.
"""

import asyncio

from mcp import ClientSession  # type: ignore[import-untyped]
from mcp.client.streamable_http import streamable_http_client  # type: ignore[import-untyped]

URL = "http://127.0.0.1:8000/mcp"


async def main():
    print(f"connecting to {URL} ...")
    try:
        async with streamable_http_client(URL) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"connected to: {init.server_info.name}")

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
