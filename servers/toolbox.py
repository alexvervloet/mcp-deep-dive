"""
servers/toolbox.py: a realistic multi-tool MCP server.

The calculator served one tool; the notes server showed all three primitives
on a small scale. This server is what a *real* MCP server looks like: a handful
of related tools a host can route between, plus a couple of resources and a
prompt, all from one process. It's the server the capstone host drives.

The point of this section is that adding capability to an MCP server is the same
move every time: write a function, describe it with a docstring + type hints,
slap `@mcp.tool()` on it. The model then discovers it automatically via
`tools/list`, and you don't change the client at all. That's the payoff of a
protocol: the server grows, every MCP-speaking host gets the new tool for free.

Tools here, chosen to exercise routing and chaining:
  - calculator   : safe arithmetic (pure, no side effects)
  - search_notes : read-only knowledge-base lookup
  - word_count   : counts words/characters in text (pure)
  - save_note    : WRITES a file (a side effect, the "dangerous" one)

Run directly to serve over stdio:

    python servers/toolbox.py

SDK note: targets the official `mcp` Python SDK 1.x (`mcp.server.fastmcp`).
"""

import ast
import operator
import os
import re

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

mcp = FastMCP("toolbox")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(REPO_ROOT, "workspace")

_KNOWLEDGE_BASE = {
    "plans": "Nimbus Notes has three plans: Free, Plus ($4/month), and Team ($10/user/month).",
    "trash": "Deleted notes are kept in Trash for 30 days before being permanently removed.",
    "data": "All Nimbus Notes customer data is stored in data centers in Frankfurt, Germany.",
    "refunds": "Annual subscriptions are refundable in full within 14 days of purchase.",
    "twofactor": "Enable two-factor authentication under Settings -> Security.",
    "export": "Any notebook can be exported to Markdown, PDF, or HTML.",
    "offline": "Offline editing is available on the Plus and Team plans, not Free.",
}

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
    """Evaluate a basic arithmetic expression like '12 * (3 + 4)'.

    Use this for any math instead of computing it yourself.
    """
    return str(_safe_eval(ast.parse(expression, mode="eval").body))


@mcp.tool()
def search_notes(query: str) -> str:
    """Search the Nimbus Notes help knowledge base.

    Use this to answer questions about the product (plans, billing, security).
    """
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for text in _KNOWLEDGE_BASE.values():
        overlap = len(q & set(re.findall(r"[a-z0-9]+", text.lower())))
        if overlap:
            scored.append((overlap, text))
    scored.sort(key=lambda p: p[0], reverse=True)
    if not scored:
        return "No matching notes found."
    return "\n".join(f"- {text}" for _, text in scored[:2])


@mcp.tool()
def word_count(text: str) -> str:
    """Count the words and characters in a piece of text."""
    words = len(re.findall(r"\S+", text))
    return f"{words} words, {len(text)} characters"


@mcp.tool()
def save_note(title: str, body: str) -> str:
    """Save a note to the user's workspace. Writes a file to disk.

    This has a side effect, so a careful host should require human approval
    before running it (see the capstone and the Security section).
    """
    os.makedirs(WORKSPACE, exist_ok=True)
    safe = re.sub(r"[^a-z0-9_-]+", "_", title.lower()).strip("_") or "note"
    path = os.path.join(WORKSPACE, safe + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{body}\n")
    return f"Saved note to workspace/{safe}.md"


@mcp.resource("notes://all")
def all_notes() -> str:
    """A directory of every knowledge-base note, by key."""
    return "\n".join(f"- {key}: {text}" for key, text in _KNOWLEDGE_BASE.items())


@mcp.resource("notes://note/{key}")
def one_note(key: str) -> str:
    """The text of a single note, by key (e.g. notes://note/plans)."""
    return _KNOWLEDGE_BASE.get(key, f"(no note named {key!r})")


@mcp.prompt()
def summarize_notes(topic: str = "everything") -> str:
    """A reusable prompt template that asks a model to summarize the notes."""
    catalog = "\n".join(f"- {key}: {text}" for key, text in _KNOWLEDGE_BASE.items())
    return (
        f"Here is the Nimbus Notes knowledge base:\n\n{catalog}\n\n"
        f"Write a short, friendly summary focused on: {topic}."
    )


if __name__ == "__main__":
    mcp.run()
