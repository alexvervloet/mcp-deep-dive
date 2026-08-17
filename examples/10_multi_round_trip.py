"""
examples/10_multi_round_trip.py: input-required flows in MCP 2026-07-28.

Modern MCP removed server-initiated requests. A tool that needs missing user
input returns `resultType: "input_required"`; the client collects answers and
retries the original call with `inputResponses` plus opaque `requestState`.
This is Multi Round-Trip Requests (MRTR).

The Python SDK hides the retry plumbing. A server expresses the dependency with
`Resolve(...)`, while the high-level Client drives the rounds and invokes its
elicitation callback. This example runs in-process, offline, with no API key.
"""

import asyncio
from typing import Annotated

from mcp import Client, types  # type: ignore[import-untyped]
from mcp.server.mcpserver import Elicit, MCPServer, Resolve  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

mcp = MCPServer("mrtr-demo", version="1.0.0")


class Quantity(BaseModel):
    quantity: int = Field(ge=1, description="Number of items")


def ask_quantity() -> Quantity | Elicit[Quantity]:
    """Return a typed question instead of reaching back over the connection."""
    return Elicit("How many widgets should I price?", Quantity)


@mcp.tool()
def quote(
    unit_price: float,
    quantity: Annotated[Quantity, Resolve(ask_quantity)],
) -> str:
    """Price widgets, asking for quantity when the caller omitted it."""
    return f"{quantity.quantity} widgets cost ${unit_price * quantity.quantity:.2f}"


async def answer_input(_context, params):
    """A real host would render params.requested_schema and ask its user."""
    print(f"client received input request: {params.message}")
    print(f"requested schema: {params.requested_schema}")
    print("simulated user answer: quantity=3")
    return types.ElicitResult(action="accept", content={"quantity": 3})


async def main():
    async with Client(mcp, elicitation_callback=answer_input) as client:
        print(f"protocol: {client.protocol_version}")
        result = await client.call_tool("quote", {"unit_price": 12.50})
        text = "".join(getattr(block, "text", "") for block in result.content)
        print(f"final tool result: {text}")
        print("The SDK completed the input_required -> answer -> retry loop.")


if __name__ == "__main__":
    asyncio.run(main())
