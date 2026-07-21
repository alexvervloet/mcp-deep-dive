"""
examples/05_prompts.py: PROMPTS: reusable templates served by MCP (offline).

The third primitive. A PROMPT is a parameterized prompt TEMPLATE that the
server owns and the user/app picks: think of the slash-commands in a chat app
("/summarize"). The server holds the wording and fills in the arguments; the
client gets back ready-to-send messages.

Why serve prompts over a protocol instead of hard-coding them in the host?
Because the server is the expert on its own data. The team that runs the notes
server can ship a great "summarize my notes" prompt, with correct field names and the
right tone, and improve it server-side without every host re-implementing it.
The host just lists what's available and offers it to the user.

The notes server offers two:
  - summarize_notes(topic="everything")
  - draft_note(title, tone="neutral")

This example lists them and renders each with arguments, still with no LLM. (You'd
then send the rendered text to a model; Section 8 does that.)

Run it (offline, no key):

    python examples/05_prompts.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.mcp_client import MCPClient, run


async def main():
    async with MCPClient("servers/notes.py") as client:

        # Discover the prompt templates (prompts/list).
        print("prompt templates the server offers:")
        for name, desc in await client.list_prompts():
            print(f"  - {name}: {desc.splitlines()[0]}")

        # Render one with its default argument (prompts/get). The SERVER decides
        # the exact text; we just supply the argument values.
        print("\nget summarize_notes(topic='billing'):")
        print("-" * 60)
        print(await client.get_prompt("summarize_notes", {"topic": "billing"}))
        print("-" * 60)

        # Another template, different arguments.
        print("\nget draft_note(title='Weekly sync', tone='upbeat'):")
        print("-" * 60)
        print(await client.get_prompt("draft_note", {"title": "Weekly sync", "tone": "upbeat"}))
        print("-" * 60)

    print("\nKey idea: the rendered text is what you'd FEED a model. The prompt")
    print("itself lives on the server, versioned and improvable independently.")


if __name__ == "__main__":
    run(main())
