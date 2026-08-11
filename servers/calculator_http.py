"""
servers/calculator_http.py: the SAME server, over HTTP instead of stdio.

This is byte-for-byte the calculator from servers/calculator.py, with ONE line
changed: the transport. Instead of `mcp.run()` (stdio), it runs
`mcp.run(transport="streamable-http")`, which starts a small web service.

That one-line swap is the whole lesson of the transports section:

  stdio            the server is a LOCAL SUBPROCESS the host launches and talks
                   to over its stdin/stdout. Great for tools that ship with an
                   app or run on your machine. No ports, no auth, dies with the
                   host. (Everything earlier in this repo used stdio.)

  streamable HTTP  the server is a NETWORK SERVICE the host connects to by URL.
                   Great for remote/shared servers, multiple clients, servers in
                   another language or another company. You now have to think
                   about ports, URLs, and (in production) authentication.

The tools, resources, and prompts you write are IDENTICAL across transports 
you choose the transport based on WHERE the server runs, not what it does.

The HTTP transport also adds something stdio never needed: a SESSION. On the
first request the server mints an id, hands it back in an `Mcp-Session-Id`
response header, and the client repeats it on every later request so the server
can find the state belonging to that connection. Fine for one process. A problem
the moment the server sits behind a load balancer, because only the replica that
minted the session can serve it.

Running with `--stateless` passes `stateless_http=True`, which turns sessions
off: no id is issued, the server keeps nothing between requests, and any replica
can answer any request. What you give up is everything that needs a standing
connection, which in practice means resumable streams and server-initiated
messages outside a request. Section 9 of the README walks through the tradeoff.

Run it (it starts a server and stays up; Ctrl-C to stop):

    python servers/calculator_http.py               # sessions on (the default)
    python servers/calculator_http.py --stateless   # sessions off
    # then, in another terminal:
    python examples/08_http_transport.py

By default MCPServer serves on http://127.0.0.1:8000/mcp.

SDK note: targets the official `mcp` Python SDK 2.x. `transport="streamable-http"`
is the current recommended HTTP transport; older docs/tutorials may show "sse",
which is the legacy Server-Sent-Events transport (see the README's transport
section).
"""

import ast
import operator
import sys

from mcp.server.mcpserver import MCPServer  # type: ignore[import-untyped]

# The constructor takes what the server IS (its name, tools, middleware). Where
# it listens is a property of a particular run, so `host`, `port`,
# `streamable_http_path` and `stateless_http` are arguments to `run()` instead.
# In SDK 1.x they were constructor settings; passing them here now raises.
mcp = MCPServer("calculator-http")

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like '12 * (3 + 4)'."""
    return str(_safe_eval(ast.parse(expression, mode="eval").body))


if __name__ == "__main__":
    # The ONLY difference from servers/calculator.py is this transport argument.
    # The tool above is untouched: whether sessions are on is a deployment
    # decision, not something the tools you write ever see.
    stateless = "--stateless" in sys.argv
    print(f"sessions: {'off (stateless_http=True)' if stateless else 'on (default)'}")
    mcp.run(transport="streamable-http", stateless_http=stateless)
