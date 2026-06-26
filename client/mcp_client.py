"""
client/mcp_client.py — a small, readable wrapper around the MCP client SDK.
==========================================================================

The official SDK's client API is asynchronous and uses two nested context
managers:

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("calculator", {"expression": "6*7"})

That's the real shape and it's worth seeing once (examples/02 uses it raw). But
typing that ceremony in every example buries the lesson, so this module wraps it
in one class, `MCPClient`, that:

  - launches a server script as a subprocess over **stdio** (the most common
    local transport),
  - runs the `initialize` handshake,
  - exposes plain methods — list/call tools, list/read resources, list/get
    prompts — that return simple Python values,
  - works both as an async context manager (for the host's event loop) AND with
    a tiny synchronous helper (`run`) so the early examples read top-to-bottom
    with no async noise.

Everything here is a thin pass-through to the SDK. Nothing is hidden — open the
SDK calls below and you'll see the exact methods the docs describe.

SDK note: targets the official `mcp` Python SDK 1.x. Imports used:
  from mcp import ClientSession, StdioServerParameters
  from mcp.client.stdio import stdio_client
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class ToolInfo:
    """The bits of a tool descriptor we care about: what the model sees."""

    name: str
    description: str
    input_schema: dict


def server_params(script: str) -> StdioServerParameters:
    """Build the launch command for one of this repo's server scripts.

    We run the server with the SAME Python interpreter that's running the client
    (`sys.executable`), so it picks up your venv and the installed `mcp` SDK.
    `script` is a path relative to the repo root, e.g. "servers/calculator.py".
    """
    return StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(REPO_ROOT, script)],
        env=os.environ.copy(),
    )


class MCPClient:
    """One live connection to one MCP server, launched over stdio.

    Use it as an async context manager:

        async with MCPClient("servers/calculator.py") as c:
            tools = await c.list_tools()
            out = await c.call_tool("calculator", {"expression": "6 * 7"})
    """

    def __init__(self, script: str):
        self._params = server_params(script)
        self._stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "MCPClient":
        # AsyncExitStack lets us open the two nested SDK context managers and
        # close them cleanly later, without hand-writing nested `async with`s.
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        # The handshake: negotiate protocol version + capabilities. Always first.
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        if self._stack:
            await self._stack.aclose()
        self._stack = None
        self.session = None

    # --- tools -------------------------------------------------------------

    async def list_tools(self) -> list[ToolInfo]:
        """Ask the server what tools it offers (the `tools/list` method)."""
        resp = await self.session.list_tools()
        return [
            ToolInfo(name=t.name, description=t.description or "", input_schema=t.inputSchema)
            for t in resp.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Invoke a tool (`tools/call`) and return its text output as a string.

        MCP tool results come back as a list of `content` blocks; for these
        text-only tools we just join the text. `result.isError` is True when the
        tool raised — we surface that inline so a caller (or model) can react.
        """
        result = await self.session.call_tool(name, arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        if getattr(result, "isError", False):
            return f"[tool error] {text}"
        return text

    # --- resources ---------------------------------------------------------

    async def list_resources(self) -> list[tuple[str, str]]:
        """List the server's static resources as (uri, name) pairs."""
        resp = await self.session.list_resources()
        return [(str(r.uri), r.name or "") for r in resp.resources]

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI (`resources/read`) and return its text."""
        resp = await self.session.read_resource(uri)
        return "".join(getattr(block, "text", "") for block in resp.contents)

    # --- prompts -----------------------------------------------------------

    async def list_prompts(self) -> list[tuple[str, str]]:
        """List the server's prompt templates as (name, description) pairs."""
        resp = await self.session.list_prompts()
        return [(p.name, p.description or "") for p in resp.prompts]

    async def get_prompt(self, name: str, arguments: dict | None = None) -> str:
        """Render a prompt template (`prompts/get`) and return its text.

        A prompt comes back as a list of role-tagged messages; for our simple
        single-message templates we join the text of each message.
        """
        resp = await self.session.get_prompt(name, arguments or {})
        parts = []
        for msg in resp.messages:
            content = msg.content
            parts.append(getattr(content, "text", "") or "")
        return "\n".join(p for p in parts if p)


def run(coro):
    """Tiny helper so synchronous example scripts can drive an async client:

        from client.mcp_client import MCPClient, run

        async def main():
            async with MCPClient("servers/calculator.py") as c:
                print(await c.call_tool("calculator", {"expression": "2+2"}))

        run(main())
    """
    return asyncio.run(coro)
