import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


class MCPClient:
    """Thin wrapper around mcp.ClientSession + stdio_client.

    Owns the transport lifecycle and exposes call_tool / list_tools
    with OpenAI-compatible JSON schemas.
    """

    def __init__(self, server_params: StdioServerParameters) -> None:
        self._server_params = server_params
        self._session: ClientSession | None = None
        self._stdio_ctx = None
        self._session_ctx = None

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """Start stdio transport and initialize the session."""
        if self._session is not None:
            return
        self._stdio_ctx = stdio_client(self._server_params)
        read, write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

    async def close(self) -> None:
        """Gracefully shut down the session and transport."""
        if self._session_ctx is not None:
            await self._session_ctx.__aexit__(None, None, None)
            self._session_ctx = None
        if self._stdio_ctx is not None:
            await self._stdio_ctx.__aexit__(None, None, None)
            self._stdio_ctx = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call an MCP tool and return a plain dict."""
        if self._session is None:
            raise RuntimeError("MCPClient is not connected. Use 'async with' or call connect() first.")
        result = await self._session.call_tool(name, arguments or {})
        content_parts = []
        for item in result.content:
            if hasattr(item, "text") and isinstance(item.text, str):
                content_parts.append(item.text)
            else:
                content_parts.append(str(item))
        return {
            "content": "\n".join(content_parts),
            "isError": result.isError,
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools and return OpenAI-compatible function definitions."""
        if self._session is None:
            raise RuntimeError("MCPClient is not connected. Use 'async with' or call connect() first.")
        tools_result = await self._session.list_tools()
        definitions = []
        for tool in tools_result.tools:
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            })
        return definitions
