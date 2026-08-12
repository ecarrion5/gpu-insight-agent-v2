"""A SYNChronous facade over the async MCP client.

The MCP client is async; the rest of my agent is sync. Rather than make everything
async, I run a private asyncio loop in a background thread and marshal calls to it.
This is the standard "sync wrapper over an async library" pattern.

Interview point: knowing WHY this is here (protocol client is async, agent loop is sync)
and being able to explain run_coroutine_threadsafe is a concurrency signal. In
production I'd keep one persistent session for the agent's lifetime -- which is exactly
what this class does (connect once in __init__, reuse, close at the end).
"""

import asyncio
import threading
from fastmcp import Client


class MCPToolProvider:
    def __init__(self, server: str):
        # `server` can be a path to a server script (spawns it over stdio) or a URL.
        self._server = server
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._client: Client | None = None
        self._call(self._connect())          # block until connected

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _call(self, coro):
        """Submit a coroutine to the background loop and wait for its result."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    async def _connect(self) -> None:
        self._client = Client(self._server)
        await self._client.__aenter__()

    def list_tool_names(self) -> list[str]:
        tools = self._call(self._client.list_tools())
        return [t.name for t in tools]

    def call_tool(self, name: str, arguments: dict) -> str:
        res = self._call(self._client.call_tool(name, arguments))
        # fastmcp returns a result object; .data holds the deserialized value
        return str(getattr(res, "data", res))

    def close(self) -> None:
        if self._client is not None:
            self._call(self._client.__aexit__(None, None, None))
        self._loop.call_soon_threadsafe(self._loop.stop)
