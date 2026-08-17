"""
examples/11_cacheable_catalogs.py: cacheable discovery in MCP 2026-07-28.

Catalog and read results carry `ttlMs` and `cacheScope`. The client may reuse a
fresh response instead of refetching it. `public` means a correctly configured
shared cache may reuse it across authorization contexts; `private` must remain
partitioned per principal. Never mark user-specific data public.

This in-process demo uses a counting cache store so the hit is visible. It is
offline and makes no model call.
"""

import asyncio

from mcp import Client  # type: ignore[import-untyped]
from mcp.client import CacheConfig  # type: ignore[import-untyped]
from mcp.client.caching import InMemoryResponseCacheStore  # type: ignore[import-untyped]
from mcp.server.caching import CacheHint  # type: ignore[import-untyped]
from mcp.server.mcpserver import MCPServer  # type: ignore[import-untyped]


class CountingStore(InMemoryResponseCacheStore):
    def __init__(self):
        super().__init__()
        self.reads = 0
        self.hits = 0
        self.writes = 0

    async def get(self, key):
        self.reads += 1
        entry = await super().get(key)
        self.hits += entry is not None
        return entry

    async def set(self, key, entry):
        self.writes += 1
        await super().set(key, entry)


mcp = MCPServer(
    "cache-demo",
    version="1.0.0",
    cache_hints={"tools/list": CacheHint(ttl_ms=60_000, scope="public")},
)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


async def main():
    store = CountingStore()
    cache = CacheConfig(
        store=store,
        partition="demo-user",
        target_id="cache-demo-server",
    )
    async with Client(mcp, cache=cache) as client:
        first = await client.list_tools()
        print(f"server hints: ttlMs={first.ttl_ms}, cacheScope={first.cache_scope}")
        print(f"after first list: reads={store.reads}, hits={store.hits}, writes={store.writes}")

        second = await client.list_tools()
        print(f"after second list: reads={store.reads}, hits={store.hits}, writes={store.writes}")
        print(f"tools served from the fresh catalog: {[tool.name for tool in second.tools]}")

        await client.list_tools(cache_mode="refresh")
        print(f"after forced refresh: reads={store.reads}, hits={store.hits}, writes={store.writes}")


if __name__ == "__main__":
    asyncio.run(main())
