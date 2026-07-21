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

Run it (it starts a server and stays up; Ctrl-C to stop):

    python servers/calculator_http.py
    # then, in another terminal:
    python examples/08_http_transport.py

By default FastMCP serves on http://127.0.0.1:8000/mcp.

SDK note: targets the official `mcp` Python SDK 1.x. `transport="streamable-http"`
is the current recommended HTTP transport; older docs/tutorials may show "sse",
which is the legacy Server-Sent-Events transport (see the README's transport
section).
"""

import ast
import operator

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

# host/port can be set here; defaults are 127.0.0.1:8000, path /mcp.
mcp = FastMCP("calculator-http")

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
    mcp.run(transport="streamable-http")
