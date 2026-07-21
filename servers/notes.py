"""
servers/notes.py: a server with all THREE MCP primitives.

The calculator server showed one primitive: a TOOL (a function the model can
*call* to take an action). MCP defines three primitives in total, and this
server demonstrates all of them over the same connection:

  1. TOOLS      actions the model can invoke. Here: `save_note` (writes a
                  file, a side effect) and `search_notes` (read-only lookup).
                  The client/model decides to call these.

  2. RESOURCES  read-only DATA the server exposes by URI, like GET endpoints.
                  The *application* decides to read a resource and put its
                  contents into the model's context. The model doesn't "call" a
                  resource the way it calls a tool. Here:
                    notes://all          -> a fixed list of all note titles
                    notes://note/{title} -> the body of one note (templated URI)

  3. PROMPTS    reusable, parameterized prompt TEMPLATES the server offers.
                  Think of them as slash-commands a user picks ("summarize this
                  notebook"); the server fills in the template and returns the
                  messages to send to the model. Here: `summarize_notes` and
                  `draft_note`.

The split between tools, resources, and prompts is about WHO is in control:
  - a tool is *model-controlled* (the model chooses to call it),
  - a resource is *application-controlled* (your app chooses to read it),
  - a prompt is *user-controlled* (the user picks it).

Run it directly to serve over stdio (a client will normally launch it):

    python servers/notes.py

SDK note: targets the official `mcp` Python SDK 1.x (`mcp.server.fastmcp`).
"""

import os
import re

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]

mcp = FastMCP("notes")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(REPO_ROOT, "workspace")

# A tiny built-in "knowledge base" so the read-only parts work with zero setup.
# (Same "Nimbus Notes" facts as the agents/RAG dives, for continuity.)
_KNOWLEDGE_BASE = {
    "plans": "Nimbus Notes has three plans: Free, Plus ($4/month), and Team ($10/user/month).",
    "trash": "Deleted notes are kept in Trash for 30 days before being permanently removed.",
    "data": "All Nimbus Notes customer data is stored in data centers in Frankfurt, Germany.",
    "refunds": "Annual subscriptions are refundable in full within 14 days of purchase.",
    "twofactor": "Enable two-factor authentication under Settings -> Security.",
    "export": "Any notebook can be exported to Markdown, PDF, or HTML.",
    "offline": "Offline editing is available on the Plus and Team plans, not Free.",
}


# === TOOLS (model-controlled actions) ======================================


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


# === RESOURCES (application-controlled, read-only data) =====================
# A resource is addressed by a URI. FastMCP registers the function under the
# URI you pass to the decorator; the return value is the resource contents.


@mcp.resource("notes://all")
def all_notes() -> str:
    """A directory of every knowledge-base note, by key.

    Static URI (no parameters): reading `notes://all` always returns this list.
    """
    return "\n".join(f"- {key}: {text}" for key, text in _KNOWLEDGE_BASE.items())


@mcp.resource("notes://note/{key}")
def one_note(key: str) -> str:
    """The text of a single note, by key. A TEMPLATED resource URI:

    the `{key}` placeholder is filled in by the reader, e.g. `notes://note/plans`.
    This is how a server exposes a whole family of resources with one function.
    """
    text = _KNOWLEDGE_BASE.get(key)
    if text is None:
        return f"(no note named {key!r}; try one of: {', '.join(_KNOWLEDGE_BASE)})"
    return text


# === PROMPTS (user-controlled templates) ===================================
# A prompt returns the text (or messages) to send to a model. The SERVER owns
# the wording; the user/app just picks the prompt and fills the arguments.


@mcp.prompt()
def summarize_notes(topic: str = "everything") -> str:
    """A reusable prompt template that asks a model to summarize the notes.

    `topic` is an argument the caller supplies. The server decides the exact
    wording, so the prompt can be improved server-side without touching clients.
    """
    catalog = "\n".join(f"- {key}: {text}" for key, text in _KNOWLEDGE_BASE.items())
    return (
        f"Here is the Nimbus Notes knowledge base:\n\n{catalog}\n\n"
        f"Write a short, friendly summary focused on: {topic}. "
        "Use plain language and at most three sentences."
    )


@mcp.prompt()
def draft_note(title: str, tone: str = "neutral") -> str:
    """A prompt template for drafting a new note with a given title and tone."""
    return (
        f"Draft a concise note titled {title!r}. "
        f"Write it in a {tone} tone, 2-4 sentences, ready to save."
    )


if __name__ == "__main__":
    mcp.run()
