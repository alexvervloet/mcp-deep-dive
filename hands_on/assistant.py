"""
hands_on/assistant.py: the capstone: a chat assistant powered entirely by MCP.

Everything in the repo, wired into one runnable command: a multi-turn assistant
whose every capability comes from an MCP server it connects to. The model holds
no tools of its own. It discovers them over the protocol (`tools/list`), and
when it wants to act, the host runs them over the protocol (`tools/call`). Swap
the server and the assistant gets new powers without touching this file. That
is the entire point of MCP, made usable.

It pulls together every earlier section:
  - a real multi-tool SERVER          (servers/toolbox.py, Section 7)
  - a CLIENT over stdio               (client/mcp_client.py, Sections 3-6)
  - an LLM HOST loop                  (host/loop.py, Section 8)
  - human approval for risky tools    (the security lesson, Section 11)
  - multi-turn memory                 (one shared history across turns)

Provider-agnostic: set PROVIDER in .env and load the key via secrun (see SECRETS.md).
The server and tool-calling are free; only the model's turns cost anything.

    # interactive chat (Ctrl-D or "quit" to exit):
    secrun python hands_on/assistant.py

    # one-shot question, then exit:
    secrun python hands_on/assistant.py "What does the Plus plan cost for a year?"

    # point at a different MCP server:
    secrun python hands_on/assistant.py --server servers/notes.py

    # auto-approve side-effecting tools (don't prompt before save_note):
    secrun python hands_on/assistant.py --yes
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env so OPENAI_API_KEY / ANTHROPIC_API_KEY are available.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from client.mcp_client import MCPClient, run
from host import providers
from host.loop import run_host

SYSTEM = (
    "You are a concise, helpful assistant for Acme Cloud. Use the available "
    "tools to answer: the calculator for any arithmetic, search_notes for "
    "product facts, and save_note to record something the user asks you to keep. "
    "Never guess at numbers or product details; look them up with a tool. If a "
    "tool fails, tell the user plainly instead of inventing an answer."
)

# Tools that have a SIDE EFFECT (write a file, etc.) and so require human
# approval before the host runs them. This is the Section 11 lesson on a live
# path: the server is code you may not have written, so gate anything dangerous.
DANGEROUS_TOOLS = ("save_note",)


def trace(kind, *args):
    """Print what the model is doing, so the MCP round-trips are visible."""
    if kind == "call":
        call = args[0]
        argstr = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
        print(f"  \033[2m→ calling {call.name}({argstr}) over MCP\033[0m")
    elif kind == "result":
        name, text = args
        shown = text if len(text) <= 120 else text[:117] + "..."
        print(f"  \033[2m  {name} → {shown}\033[0m")


def approve(call) -> bool:
    """Human-in-the-loop: ask before running a side-effecting tool."""
    argstr = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
    print(f"\n  ⚠  The assistant wants to run: {call.name}({argstr})")
    try:
        answer = input("  Allow it? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


async def main():
    parser = argparse.ArgumentParser(description="An MCP-powered chat assistant.")
    parser.add_argument("question", nargs="*", help="A one-shot question; omit for interactive chat.")
    parser.add_argument("--server", default="servers/toolbox.py", help="MCP server script to connect to.")
    parser.add_argument("--yes", action="store_true", help="Auto-approve side-effecting tools (no prompt).")
    parser.add_argument("--max-steps", type=int, default=8, help="Tool-call ceiling per question.")
    args = parser.parse_args()

    providers.ensure_ready()  # checks PROVIDER + key; exits with guidance if missing

    approve_cb = None if args.yes else approve
    history: list = []  # shared across turns → the assistant remembers the chat

    async with MCPClient(args.server) as client:
        tools = await client.list_tools()
        print(f"provider: {providers.describe()}")
        print(f"server:   {args.server}  ({len(tools)} tools: {', '.join(t.name for t in tools)})\n")

        async def ask(question: str):
            result = await run_host(
                client,
                SYSTEM,
                question,
                max_steps=args.max_steps,
                approve=approve_cb,
                dangerous_tools=DANGEROUS_TOOLS,
                on_event=trace,
                history=history,
            )
            print(f"\nassistant: {result.answer}\n")

        # One-shot mode: answer the argv question and exit.
        if args.question:
            await ask(" ".join(args.question))
            return

        # Interactive mode: a tiny REPL with persistent memory.
        print("Chatting with an MCP-powered assistant. Ctrl-D or 'quit' to exit.\n")
        while True:
            try:
                question = input("you: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if question.lower() in ("quit", "exit"):
                break
            if not question:
                continue
            await ask(question)


if __name__ == "__main__":
    run(main())
