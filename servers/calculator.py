"""
servers/calculator.py — your first MCP server: one tool, over stdio.
====================================================================

This is the smallest useful MCP server. It exposes exactly ONE tool —
`calculator` — and nothing else. Everything that makes it an "MCP server" comes
from the official SDK's high-level `FastMCP` class:

  - `@mcp.tool()` turns a plain Python function into a tool the server
    advertises. The function's NAME becomes the tool name, its DOCSTRING becomes
    the description the model sees, and its TYPE HINTS become the input JSON
    Schema. (That is the same "a tool is a name, a description, and a schema"
    idea from the agents dive — the SDK just derives the schema for you.)
  - `mcp.run()` starts the server speaking the protocol. With no arguments it
    uses the **stdio** transport: it reads JSON-RPC requests on stdin and writes
    responses on stdout. That is exactly what a client (or a host like Claude
    Desktop) launches and talks to.

There is NO LLM here. A server just answers protocol requests. You can run it
directly and it will sit waiting on stdin:

    python servers/calculator.py

But you normally don't talk to it by hand — a client launches it as a
subprocess and drives it. See examples/02 and examples/03.

SDK note: targets the official `mcp` Python SDK 1.x (`mcp.server.fastmcp`).
"""

import ast
import operator

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

# Create the server. The name is metadata the client sees during the handshake
# ("which server am I talking to?"). Pick something recognizable.
mcp = FastMCP("calculator")


# --- a safe arithmetic evaluator (NOT Python's eval) -----------------------
# Same approach as the agents dive: parse to an AST and walk only arithmetic
# nodes, so a hostile expression can't run arbitrary code. A tool runs on YOUR
# machine when a client (or model) asks — keep it safe by construction.

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
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
    """Evaluate a basic arithmetic expression like '12 * (3 + 4)'.

    Use this for any math instead of computing it yourself.
    """
    # The docstring above is NOT just for humans: FastMCP sends it to the client
    # as the tool's `description`, and the `expression: str` hint becomes the
    # input schema {"expression": {"type": "string"}}. That text is the model's
    # only clue for when and how to call this tool — so it's prompt engineering.
    return str(_safe_eval(ast.parse(expression, mode="eval").body))


if __name__ == "__main__":
    # Default transport is stdio. This call blocks, serving requests until the
    # client closes the connection. Anything you print() would corrupt the
    # stdout protocol channel — so don't; FastMCP logs to stderr for you.
    mcp.run()
