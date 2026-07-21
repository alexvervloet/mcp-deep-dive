"""
host/providers.py: the ONLY provider-specific file (mirrors the agents dive).

A host that drives an LLM is provider-agnostic: the loop, the MCP plumbing, the
control logic are all the same regardless of which model you use. The one thing
that genuinely differs is the *shape* of a tool-calling turn: how you describe
tools, how the model hands back a tool request, and how you send a result back.
This file normalizes all of that to a tiny neutral interface the host uses:

  to_tool_schema(tools)            -> the provider's tool format
  run_turn(system, history, tools) -> a normalized Turn (text and/or tool calls)
  format_tool_results(results)     -> provider-native messages to append
  user_message(text)               -> a provider-native user message

This is the same abstraction (and the same model IDs) as the agents deep dive 
on purpose. Here, the `tools` we pass in are derived from an MCP server's
`tools/list` rather than imported from a local module, but the provider code
can't tell the difference: a tool is a name + description + JSON Schema either
way. That's the whole point of MCP: the tool's *origin* is invisible to the
model.
"""

import json
import os
from dataclasses import dataclass
from functools import lru_cache

# Same model IDs as the sibling DeepDives: don't invent new ones.
_OPENAI_CHAT = "gpt-4o-mini"
_CLAUDE_CHAT = "claude-haiku-4-5"
_KEYS = {"openai": ["OPENAI_API_KEY"], "claude": ["ANTHROPIC_API_KEY"]}


@dataclass
class ToolSpec:
    """A neutral tool descriptor. We build these from an MCP server's tool list
    (name + description + inputSchema), then convert to the provider's format.
    Identical idea to the agents dive's Tool, minus the local `func`. Here the
    function lives on the server and is invoked over the protocol."""

    name: str
    description: str
    parameters: dict  # a JSON Schema


@dataclass
class ToolCall:
    """A normalized request from the model to run one tool."""

    id: str
    name: str
    arguments: dict


@dataclass
class Turn:
    """One assistant turn, normalized. `tool_calls` empty means the model is
    done and `text` is the final answer. `raw_assistant` is the provider-native
    message to append to history (the host treats it as opaque)."""

    text: str | None
    tool_calls: list[ToolCall]
    raw_assistant: object


def provider_name() -> str:
    return os.getenv("PROVIDER", "openai").strip().lower()


def required_keys() -> list[str]:
    return _KEYS.get(provider_name(), [])


def describe() -> str:
    p = provider_name()
    if p == "openai":
        return f"openai  (chat={_OPENAI_CHAT})"
    if p == "claude":
        return f"claude  (chat={_CLAUDE_CHAT})"
    return f"unknown provider {p!r}"


def ensure_ready() -> None:
    import sys

    p = provider_name()
    if p not in _KEYS:
        sys.exit(f"PROVIDER={p!r} is not recognized. Set PROVIDER=openai or claude in .env.")
    missing = [k for k in required_keys() if not os.getenv(k)]
    if missing:
        sys.exit(
            f"PROVIDER={p} needs {', '.join(missing)} in the environment. "
            f"Provide them via secrun (see SECRETS.md), or run `secrun python check_setup.py`. "
            f"(The offline examples need no key; this is only for the host.)"
        )


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    return OpenAI()


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()


def user_message(text: str) -> dict:
    """A plain user message, same shape on both providers."""
    return {"role": "user", "content": text}


def to_tool_schema(tools: list[ToolSpec]) -> list:
    """Convert neutral ToolSpecs to the active provider's tool format."""
    p = provider_name()
    if p == "openai":
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in tools
        ]
    if p == "claude":
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
    raise ValueError(f"Unknown PROVIDER={p!r}.")


def run_turn(system: str, history: list, tool_schema: list) -> Turn:
    """Run one assistant turn and normalize the result to a Turn."""
    p = provider_name()
    if p == "openai":
        messages = [{"role": "system", "content": system}, *history]
        resp = _openai_client().chat.completions.create(
            model=_OPENAI_CHAT, messages=messages, tools=tool_schema or None  # type: ignore[arg-type]
        )
        msg = resp.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            if tc.type != "function":
                continue
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return Turn(text=msg.content, tool_calls=calls, raw_assistant=msg)

    if p == "claude":
        resp = _anthropic_client().messages.create(
            model=_CLAUDE_CHAT, max_tokens=1024, system=system, messages=history, tools=tool_schema
        )
        calls, text_parts = [], []
        for block in resp.content:
            if block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
            elif block.type == "text":
                text_parts.append(block.text)
        return Turn(
            text="".join(text_parts) or None,
            tool_calls=calls,
            raw_assistant={"role": "assistant", "content": resp.content},
        )

    raise ValueError(f"Unknown PROVIDER={p!r}.")


def format_tool_results(results: list[tuple[str, str]]) -> list:
    """Turn (tool_call_id, result_text) pairs into provider-native messages.

    OpenAI wants one `role:"tool"` message per result; Claude wants a SINGLE
    user message containing all the `tool_result` blocks. Getting this wrong is
    a classic bug, so it lives in exactly one place."""
    p = provider_name()
    if p == "openai":
        return [{"role": "tool", "tool_call_id": cid, "content": content} for cid, content in results]
    if p == "claude":
        return [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": cid, "content": content}
                    for cid, content in results
                ],
            }
        ]
    raise ValueError(f"Unknown PROVIDER={p!r}.")
