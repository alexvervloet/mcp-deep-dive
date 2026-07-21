"""
host/loop.py: the host loop: an LLM that calls MCP tools.

This is where MCP meets the agent loop. If you did the agents deep dive, the
loop is identical (model picks a tool, you run it, you feed the result back,
repeat) with ONE change: the tools come from an MCP server (`tools/list`) and
are executed over the protocol (`tools/call`) instead of being local Python
functions. The model can't tell the difference; that's the entire payoff.

The flow:
  1. Connect to an MCP server and call `list_tools()`.
  2. Turn each MCP tool descriptor into a neutral `ToolSpec` (name + description
     + JSON Schema), the SAME object the provider layer already knows how to
     describe to a model.
  3. Run the loop: ask the model; if it requests tools, call them OVER MCP and
     feed results back; stop when it answers with no tool calls.

Control logic carried over from the agents dive, because a tool over a protocol
is still a tool you must run safely:
  - max_steps: a hard ceiling so a confused model can't loop forever.
  - approval:  side-effecting tools (here, anything whose name is in
               `dangerous_tools`) can be gated behind an `approve` callback 
               the human-in-the-loop. This matters MORE with MCP, because the
               server is code you may not have written.
  - errors:    a failing tool returns its error text as the result, so the model
               can adapt instead of crashing the host.

Everything is async because the MCP client is async; the capstone wraps this in
a CLI.
"""

import asyncio
from dataclasses import dataclass, field

from . import providers
from .providers import ToolSpec


@dataclass
class Step:
    """A record of one tool execution, for tracing and inspection."""

    tool: str
    arguments: dict
    result: str
    approved: bool = True


@dataclass
class HostResult:
    answer: str
    steps: list[Step] = field(default_factory=list)
    stopped_early: bool = False


def mcp_tools_to_specs(tools) -> list[ToolSpec]:
    """Convert MCP tool descriptors (from MCPClient.list_tools) into the neutral
    ToolSpec the provider layer understands. This three-line function is the
    whole bridge between 'a tool served over MCP' and 'a tool the model can
    call'. The inputSchema is already JSON Schema, so it passes straight through."""
    return [
        ToolSpec(name=t.name, description=t.description, parameters=t.input_schema)
        for t in tools
    ]


async def run_host(
    client,
    system: str,
    user_input: str,
    *,
    max_steps: int = 6,
    approve=None,
    dangerous_tools: tuple[str, ...] = (),
    on_event=None,
    history: list | None = None,
) -> HostResult:
    """Drive the model against one connected MCP `client` until it answers.

    - `client`: a connected MCPClient (see client/mcp_client.py).
    - `approve`: optional callback `(ToolCall) -> bool`, consulted before running
      any tool whose name is in `dangerous_tools`. Return False to deny.
    - `dangerous_tools`: tool names that require approval (e.g. ("save_note",)).
    - `on_event`: optional callback for tracing; called with ("call", ToolCall)
      and ("result", name, text).
    - `history`: optional message list for multi-turn memory (re-send the same
      list across calls).
    """
    # 1) Discover the server's tools and describe them to the model.
    mcp_tools = await client.list_tools()
    specs = mcp_tools_to_specs(mcp_tools)
    tool_schema = providers.to_tool_schema(specs)
    by_name = {s.name: s for s in specs}

    if history is None:
        history = []
    history.append(providers.user_message(user_input))
    steps: list[Step] = []

    for _ in range(max_steps):
        # run_turn is sync (the provider SDKs are sync); run it off the event
        # loop so we don't block other async work.
        turn = await asyncio.to_thread(providers.run_turn, system, history, tool_schema)
        history.append(turn.raw_assistant)

        if not turn.tool_calls:
            return HostResult(answer=turn.text or "", steps=steps)

        results = []
        for call in turn.tool_calls:
            if on_event:
                on_event("call", call)
            approved = True

            if call.name not in by_name:
                result = f"Error: the server has no tool named {call.name!r}."
            elif call.name in dangerous_tools and approve is not None and not approve(call):
                approved = False
                result = "Error: the user denied permission to run this tool."
            else:
                # THE MCP CALL: execute the model's requested tool over the
                # protocol. The wrapper returns text (and surfaces tool errors
                # in-band as "[tool error] ..."), so a failure feeds back to the
                # model as a result instead of crashing the host.
                result = await client.call_tool(call.name, call.arguments)

            if on_event:
                on_event("result", call.name, result)
            steps.append(Step(tool=call.name, arguments=call.arguments, result=result, approved=approved))
            results.append((call.id, result))

        history += providers.format_tool_results(results)

    return HostResult(
        answer="(stopped: reached the step limit without finishing)",
        steps=steps,
        stopped_early=True,
    )
