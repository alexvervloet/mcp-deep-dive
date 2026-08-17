"""
examples/08_http_transport.py: modern MCP over HTTP (offline, no key).

MCP 2026-07-28 removed the initialize handshake and Mcp-Session-Id. Each
request is self-describing, so any replica can handle it. This example shows
that twice:

1. The SDK's high-level Client connects by URL, lists tools, and calls one.
2. A raw HTTP tools/call displays the required routing headers and confirms
   that the response contains no protocol session id.

TWO TERMINALS:

  terminal 1:  python servers/calculator_http.py
  terminal 2:  python examples/08_http_transport.py

No LLM and no key are involved.
"""

import asyncio
import json
import urllib.request

from mcp import Client  # type: ignore[import-untyped]

URL = "http://127.0.0.1:8000/mcp"
PROTOCOL_VERSION = "2026-07-28"
REQUEST_META = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {
        "name": "08-http-transport",
        "version": "1.0.0",
    }
}


async def sdk_call() -> bool:
    """Use the recommended high-level client; a URL selects Streamable HTTP."""
    print(f"connecting to {URL} ...")
    try:
        async with Client(URL) as client:
            print(f"protocol: {client.protocol_version} (no initialize handshake)")
            tools = await client.list_tools()
            print(f"tools: {[tool.name for tool in tools.tools]}")
            result = await client.call_tool("calculator", {"expression": "111 * 3"})
            text = "".join(getattr(block, "text", "") for block in result.content)
            print(f"calculator('111 * 3') -> {text}")
    except Exception as exc:  # almost always: the server is not running yet
        print(f"\ncould not connect ({exc!r}).")
        print("Start the server first, in another terminal:")
        print("    python servers/calculator_http.py")
        return False
    return True


def raw_call(url: str = URL) -> None:
    """Send one self-contained 2026-07-28 request using only stdlib HTTP."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "calculator",
            "arguments": {"expression": "20 + 22"},
            "_meta": REQUEST_META,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "calculator",
    }
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        response_body = response.read().decode()
        session_id = response.headers.get("mcp-session-id")

    print("\nraw HTTP request routing headers:")
    for name in ("MCP-Protocol-Version", "Mcp-Method", "Mcp-Name"):
        print(f"  {name}: {headers[name]}")
    print(f"response body: {response_body}")
    print(f"Mcp-Session-Id: {session_id!r}  <- modern MCP does not issue one")
    print("Any replica may serve the next request; application state must be explicit.")


if __name__ == "__main__":
    if asyncio.run(sdk_call()):
        raw_call()
