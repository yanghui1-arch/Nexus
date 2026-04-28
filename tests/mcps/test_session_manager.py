from unittest.mock import AsyncMock, patch
import pytest
from src.mcps.session_manager import MCPSessionManager
from src.mcps.client import MCPClient
from mcp import StdioServerParameters


def _mock():
    m = AsyncMock(spec=MCPClient)
    m.connect, m.close, m.call_tool, m.list_tools = AsyncMock(), AsyncMock(), AsyncMock(return_value={"c":"ok","e":False}), AsyncMock(return_value=[{"type":"function","function":{"name":"f","d":"","p":{}}}])
    return m


async def test_register_get():
    with patch("src.mcps.session_manager.MCPClient", return_value=_mock()):
        mg = MCPSessionManager(); mg.register("f", StdioServerParameters(command="p", args=[]))
        assert mg.get_client("f") is not None


async def test_dup_raises():
    mg = MCPSessionManager(); mg.register("a", StdioServerParameters(command="p", args=[]))
    with pytest.raises(ValueError, match="already registered"): mg.register("a", StdioServerParameters(command="p", args=[]))


async def test_missing_raises():
    with pytest.raises(KeyError, match="not found"): MCPSessionManager().get_client("x")


async def test_tool_definitions():
    with patch("src.mcps.session_manager.MCPClient", return_value=_mock()):
        mg = MCPSessionManager(); mg.register("f", StdioServerParameters(command="p", args=[])); d = await mg.get_all_tool_definitions()
    assert d[0]["function"]["name"] == "f"


async def test_callables():
    m = _mock()
    with patch("src.mcps.session_manager.MCPClient", return_value=m):
        mg = MCPSessionManager(); mg.register("f", StdioServerParameters(command="p", args=[])); c = mg.get_all_callables()
    assert c["f"] is m.call_tool


async def test_close_all():
    m = _mock()
    with patch("src.mcps.session_manager.MCPClient", return_value=m):
        mg = MCPSessionManager(); mg.register("f", StdioServerParameters(command="p", args=[])); await mg.close_all()
    m.close.assert_awaited_once()


async def test_context_manager():
    m = _mock()
    with patch("src.mcps.session_manager.MCPClient", return_value=m):
        mg = MCPSessionManager(); mg.register("f", StdioServerParameters(command="p", args=[]))
        async with mg: pass
    m.close.assert_awaited_once()
