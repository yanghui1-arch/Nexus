from typing import Any, Callable
from mcp import StdioServerParameters
from .client import MCPClient


class MCPSessionManager:
    """Manages multiple MCPClient instances keyed by a logical name."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}

    async def __aenter__(self) -> "MCPSessionManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close_all()

    def register(self, name: str, server_params: StdioServerParameters) -> None:
        if name in self._clients:
            raise ValueError(f"MCP client '{name}' is already registered.")
        self._clients[name] = MCPClient(server_params)

    def get_client(self, name: str) -> MCPClient:
        if name not in self._clients:
            raise KeyError(f"MCP client '{name}' not found.")
        return self._clients[name]

    async def get_all_tool_definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for client in self._clients.values():
            await client.connect()
            definitions.extend(await client.list_tools())
        return definitions

    def get_all_callables(self) -> dict[str, Callable]:
        return {name: client.call_tool for name, client in self._clients.items()}

    async def close_all(self) -> None:
        for client in self._clients.values():
            await client.close()
