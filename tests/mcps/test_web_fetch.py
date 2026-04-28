from unittest.mock import AsyncMock, patch
import pytest
from src.mcps.web_fetch import web_fetch


def _mock(content: str | None, is_error: bool = False):
    m = AsyncMock(); m.call_tool.return_value = {"content": content or "", "isError": is_error}
    cm = AsyncMock(); cm.__aenter__.return_value = m; cm.__aexit__.return_value = None
    return cm, m


@pytest.fixture
def patch_mcp():
    def _p(content, is_error=False):
        cm, m = _mock(content, is_error)
        return patch("src.mcps.web_fetch.MCPClient", return_value=cm), m
    return _p


async def test_successful_fetch(patch_mcp):
    p, m = patch_mcp("# Hello")
    with p: r = await web_fetch("https://example.com")
    assert r["success"] and "Hello" in r["content"]


async def test_passes_arguments(patch_mcp):
    p, m = patch_mcp("content")
    with p: await web_fetch("https://example.com", max_length=1000, start_index=500, raw=True)
    m.call_tool.assert_awaited_once_with("fetch", {"url": "https://example.com", "max_length": 1000, "start_index": 500, "raw": True})


async def test_empty_content_returns_failure(patch_mcp):
    p, _ = patch_mcp(None)
    with p: r = await web_fetch("https://example.com")
    assert not r["success"] and "No content" in r["message"]


async def test_exception_returns_failure():
    with patch("src.mcps.web_fetch.MCPClient", side_effect=Exception("crash")):
        r = await web_fetch("https://example.com")
    assert not r["success"] and "crash" in r["message"]


async def test_default_arguments(patch_mcp):
    p, m = patch_mcp("content")
    with p: await web_fetch("https://example.com")
    a = m.call_tool.call_args[0][1]
    assert a["max_length"] == 5000 and a["start_index"] == 0 and a["raw"] is False


async def test_is_error_returns_failure(patch_mcp):
    p, _ = patch_mcp("bad", is_error=True)
    with p: r = await web_fetch("https://example.com")
    assert not r["success"] and "bad" in r["message"]
