"""
servers/calculator_http.py: the calculator server over Streamable HTTP.

The tool is identical to servers/calculator.py; only `mcp.run()` selects a
network transport. Run this in one terminal and examples/08_http_transport.py
in another:

    python servers/calculator_http.py

The endpoint is http://127.0.0.1:8000/mcp by default.

MCP 2026-07-28 has no initialize handshake and no protocol-level session.
`stateless_http=True` is therefore not a modern-mode switch: in SDK v2 it only
changes how pre-2026 legacy clients are served. Modern requests are already
self-contained and can land on any replica.
"""

import ast
import operator

from mcp.server.mcpserver import MCPServer  # type: ignore[import-untyped]

mcp = MCPServer("calculator-http", version="1.0.0")

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
    """Evaluate a basic arithmetic expression like '12 * (3 + 4)'."""
    return str(_safe_eval(ast.parse(expression, mode="eval").body))


if __name__ == "__main__":
    print("modern MCP 2026-07-28: no handshake, no Mcp-Session-Id")
    mcp.run(transport="streamable-http")
