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

That dropped getter is a clue about the one thing HTTP has and stdio does not: a
SESSION. After the SDK part, this file drops to the raw HTTP level (the same
move as example 01, look at the bytes) and prints whether the server issued an
`Mcp-Session-Id` header. Run the whole thing twice:

  terminal 1:  python servers/calculator_http.py               # sessions on
  terminal 1:  python servers/calculator_http.py --stateless   # sessions off

The tool calls come out identical both times. Only the header changes, and with
it the answer to "can a second replica of this server handle my next request?"
"""

import asyncio
import json
import urllib.request

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
        return False
    return True


def show_session(url: str = URL) -> None:
    """Send one raw `initialize` and report the session id, if there is one.

    The SDK client hides this, so we use stdlib HTTP: a plain POST with the
    JSON-RPC body example 01 walked through. A stateful server answers with an
    `Mcp-Session-Id` header that every later request has to echo back; a
    stateless one has no id to give.
    """
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "08_http_transport", "version": "0"},
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        session_id = response.headers.get("mcp-session-id")

    if session_id:
        print(f"\nsession: the server issued Mcp-Session-Id {session_id}")
        print("  State for this connection lives in THAT server process, so the")
        print("  replica that answered here has to answer everything after it.")
        # A session is a resource with a lifetime, so end the one we just made.
        end = urllib.request.Request(url, method="DELETE",
                                     headers={"Mcp-Session-Id": session_id})
        with urllib.request.urlopen(end, timeout=10) as response:
            print(f"  DELETE (end the session) -> {response.status}")
        print("\n  Now restart the server with --stateless and run this again.")
    else:
        print("\nsession: none, the server issued no Mcp-Session-Id")
        print("  Every request carries what it needs and the server keeps nothing")
        print("  between them, so any replica behind a load balancer can serve any")
        print("  request. The cost is anything needing a standing connection:")
        print("  no resumable streams, and no server-to-client requests like")
        print("  sampling, because the reply would have nowhere to land.")


if __name__ == "__main__":
    if asyncio.run(main()):
        show_session()
