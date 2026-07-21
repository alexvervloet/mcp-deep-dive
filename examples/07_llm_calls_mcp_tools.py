"""
examples/07_llm_calls_mcp_tools.py: put an LLM in the loop (NEEDS A KEY).

This is the first example that costs money. Everything before it was offline.
Now we let a MODEL drive the MCP tools: the host lists the server's tools,
describes them to the model, and when the model asks to call one, the host runs
it over the protocol and feeds the result back: the agent loop, but the tools
live in a separate process behind MCP.

The headline: the model has NO idea the tools came from an MCP server. To it,
they're just names + descriptions + schemas. We built `ToolSpec` from the
server's `tools/list`, handed those to the provider exactly like local tools,
and the loop runs unchanged. That invisibility is the reason MCP exists: write
the server once, and any model on any provider can use it.

Provider-agnostic: set PROVIDER in .env and load the key via secrun (see SECRETS.md).

    # one-off question that needs a tool
    secrun python examples/07_llm_calls_mcp_tools.py

Try changing the question to one that needs two tools (search then math) and
watch the model chain calls.
"""

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
    "You are a helpful assistant. Use the available tools to answer. "
    "Use the calculator for any arithmetic and search_notes for product facts; "
    "don't guess."
)


def trace(kind, *args):
    if kind == "call":
        call = args[0]
        argstr = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
        print(f"  -> model calls {call.name}({argstr})")
    elif kind == "result":
        name, text = args
        shown = text if len(text) <= 100 else text[:97] + "..."
        print(f"     {name} returned: {shown}")


async def main():
    providers.ensure_ready()  # checks PROVIDER + key; exits with guidance if missing
    print(f"provider: {providers.describe()}\n")

    question = "What does the Plus plan cost per year?"
    print(f"question: {question}\n")

    async with MCPClient("servers/toolbox.py") as client:
        result = await run_host(client, SYSTEM, question, on_event=trace)

    print(f"\nanswer: {result.answer}")
    print(f"(took {len(result.steps)} tool call(s) over MCP)")


if __name__ == "__main__":
    run(main())
