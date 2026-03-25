from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcps.web_fetch import web_fetch


def _make_mocks(content_text: str | None):
    """Build the nested async context manager mocks for stdio_client + ClientSession."""
    # call_tool result
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text=content_text)] if content_text is not None else []

    # ClientSession
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = mock_result
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    # stdio_client
    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
    mock_stdio_cm.__aexit__.return_value = None

    return mock_stdio_cm, mock_session_cm, mock_session


@pytest.fixture
def patch_mcp():
    """Patch both MCP transport and session."""
    def _patch(content_text: str | None):
        mock_stdio_cm, mock_session_cm, mock_session = _make_mocks(content_text)
        stdio_patch = patch("src.mcps.web_fetch.stdio_client", return_value=mock_stdio_cm)
        session_patch = patch("src.mcps.web_fetch.ClientSession", return_value=mock_session_cm)
        return stdio_patch, session_patch, mock_session
    return _patch


async def test_successful_fetch(patch_mcp):
    stdio_patch, session_patch, mock_session = patch_mcp("# Hello\nThis is the page content.")

    with stdio_patch, session_patch:
        result = await web_fetch("https://example.com")

    assert result["success"] is True
    assert result["url"] == "https://example.com"
    assert "Hello" in result["content"]


async def test_passes_arguments_to_mcp(patch_mcp):
    stdio_patch, session_patch, mock_session = patch_mcp("content")

    with stdio_patch, session_patch:
        await web_fetch("https://example.com", max_length=1000, start_index=500, raw=True)

    mock_session.call_tool.assert_awaited_once_with(
        "fetch",
        {"url": "https://example.com", "max_length": 1000, "start_index": 500, "raw": True},
    )


async def test_empty_content_returns_failure(patch_mcp):
    stdio_patch, session_patch, _ = patch_mcp(None)

    with stdio_patch, session_patch:
        result = await web_fetch("https://example.com")

    assert result["success"] is False
    assert result["content"] == ""
    assert "No content returned" in result["message"]


async def test_mcp_exception_returns_failure():
    with patch("src.mcps.web_fetch.stdio_client", side_effect=Exception("server crashed")):
        result = await web_fetch("https://example.com")

    assert result["success"] is False
    assert result["content"] == ""
    assert "server crashed" in result["message"]


async def test_default_arguments(patch_mcp):
    stdio_patch, session_patch, mock_session = patch_mcp("content")

    with stdio_patch, session_patch:
        await web_fetch("https://example.com")

    _, call_kwargs = mock_session.call_tool.call_args
    args = mock_session.call_tool.call_args[0][1]
    assert args["max_length"] == 5000
    assert args["start_index"] == 0
    assert args["raw"] is False
