from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.mcps.client import MCPClient
from mcp import StdioServerParameters
from mcp.types import TextContent


def _mock(content_text: str | None):
    result = MagicMock()
    result.content = [TextContent(text=content_text, type="text")] if content_text is not None else []
    result.isError = False
    session = AsyncMock()
    session.call_tool.return_value = result
    tool = MagicMock()
    tool.name = "fetch"
    tool.description = "Fetch a URL"
    tool.inputSchema = {"type": "object"}
    session.list_tools.return_value = MagicMock(tools=[tool])
    sc = AsyncMock()
    sc.__aenter__.return_value = (AsyncMock(), AsyncMock())
    sc.__aexit__.return_value = None
    sm = AsyncMock()
    sm.__aenter__.return_value = session
    sm.__aexit__.return_value = None
    return patch("src.mcps.client.stdio_client", return_value=sc), patch("src.mcps.client.ClientSession", return_value=sm), session


async def test_connect_and_close():
    sp, cp, _ = _mock("ok")
    client = MCPClient(StdioServerParameters(command="python", args=["-m", "test"]))
    with sp, cp:
        await client.connect()
        assert client._session is not None
        await client.close()
        assert client._session is None


async def test_context_manager():
    sp, cp, session = _mock("data")
    params = StdioServerParameters(command="python", args=["-m", "test"])
    with sp, cp:
        async with MCPClient(params) as client:
            result = await client.call_tool("fetch", {"url": "https://example.com"})
    assert result == {"content": "data", "isError": False}
    session.call_tool.assert_awaited_once_with("fetch", {"url": "https://example.com"})


async def test_call_tool_not_connected():
    client = MCPClient(StdioServerParameters(command="python", args=["-m", "test"]))
    with pytest.raises(RuntimeError, match="not connected"):
        await client.call_tool("fetch", {})


async def test_list_tools():
    sp, cp, _ = _mock("ok")
    client = MCPClient(StdioServerParameters(command="python", args=["-m", "test"]))
    with sp, cp:
        await client.connect()
        defs = await client.list_tools()
    assert len(defs) == 1
    assert defs[0]["type"] == "function"
    assert defs[0]["function"]["name"] == "fetch"
