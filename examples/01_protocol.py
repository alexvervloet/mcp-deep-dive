"""
examples/01_protocol.py: the protocol in one page (offline, no key).

Before launching anything, get the mental model. MCP is a small, boring idea:

  HOST            the app the user interacts with (Claude Desktop, an IDE, the
                  capstone in this repo). It contains one or more CLIENTS.
  CLIENT          a connector inside the host that holds ONE connection to ONE
                  server and speaks the protocol.
  SERVER          a separate program that exposes tools/resources/prompts. It
                  does NOT contain a model; it just answers requests.

They talk over **JSON-RPC 2.0**, plain JSON request/response messages, across
a TRANSPORT (a pipe). The two transports you'll meet: stdio (a local subprocess,
default in this repo) and streamable HTTP/SSE (a network service; Section 9).

The conversation always starts with a HANDSHAKE: the client sends `initialize`,
the server replies with its name and CAPABILITIES (which of the three primitives
it offers). After that, the client can ask for and use:

  TOOLS      tools/list, tools/call           (model-controlled actions)
  RESOURCES  resources/list, resources/read   (app-controlled read-only data)
  PROMPTS    prompts/list, prompts/get        (user-controlled templates)

That's the whole protocol surface you'll use. This script doesn't talk to a
server. It just prints example JSON-RPC messages so the *shape* is familiar
before example 02 sends real ones. No model, no key, no network.
"""

import json


def show(title, obj):
    print(f"\n{title}")
    print(json.dumps(obj, indent=2))


def main():
    print("=" * 70)
    print("MCP in one page: the messages a client and server exchange")
    print("=" * 70)

    print("\n1) The client opens the connection with a handshake.")
    show("client -> server  (initialize)", {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
    })
    show("server -> client  (here's who I am + what I offer)", {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "serverInfo": {"name": "calculator", "version": "1.x"},
            "capabilities": {"tools": {}},
        },
    })

    print("\n2) The client asks what tools exist.")
    show("client -> server  (tools/list)", {
        "jsonrpc": "2.0", "id": 2, "method": "tools/list",
    })
    show("server -> client  (a tool = name + description + inputSchema)", {
        "jsonrpc": "2.0", "id": 2,
        "result": {"tools": [{
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression...",
            "inputSchema": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        }]},
    })

    print("\n3) The client calls a tool. (A model would *ask* the host to do this.)")
    show("client -> server  (tools/call)", {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "calculator", "arguments": {"expression": "6 * 7"}},
    })
    show("server -> client  (result as content blocks)", {
        "jsonrpc": "2.0", "id": 3,
        "result": {"content": [{"type": "text", "text": "42"}], "isError": False},
    })

    print("\n" + "-" * 70)
    print("That's it. Resources (resources/list + resources/read) and prompts")
    print("(prompts/list + prompts/get) follow the same request/response shape.")
    print("You will NOT hand-write this JSON; the SDK does it. But every example")
    print("from here on is just these messages flying over a pipe.")
    print("\nNext: python examples/02_first_server_and_client.py  (real messages)")


if __name__ == "__main__":
    main()
