from __future__ import annotations

from types import SimpleNamespace

import anyio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import web_search as web_search_module


class FakeStream:
    def __init__(self, events):
        """Initialize the test helper."""
        self._events = events

    def __aiter__(self):
        """Return the async iterator."""
        self._iter = iter(self._events)
        return self

    async def __anext__(self):
        """Return the next async stream item."""
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def test_openai_web_search_stream_collects_answer_and_citations():
    """Verify openai web search stream collects answer and citations."""
    annotation = MagicMock()
    annotation.model_dump.return_value = {"type": "url_citation", "url": "https://example.com"}
    fake_client = MagicMock()
    fake_client.responses.create = AsyncMock(
        return_value=FakeStream(
            [
                SimpleNamespace(type="response.output_text.delta", delta="hello "),
                SimpleNamespace(type="response.output_text.annotation.added", annotation=annotation),
                SimpleNamespace(type="response.output_text.delta", delta="world"),
            ]
        )
    )

    settings = SimpleNamespace(
        base_url="https://api.example.com/v1",
        api_key="api-key",
        model="gpt-test",
    )

    with (
        patch("src.tools.web_search.AsyncOpenAI", return_value=fake_client) as openai_cls,
        patch("src.tools.web_search.get_settings", return_value=settings),
    ):
        async def run_search():
            """Run the search test body."""
            return await web_search_module.web_search("nexus growth", max_results=3)

        result = anyio.run(run_search)

    openai_cls.assert_called_once_with(base_url="https://api.example.com/v1", api_key="api-key")

    assert result == {
        "success": True,
        "query": "nexus growth",
        "answer": "hello world",
        "citations": [{"type": "url_citation", "url": "https://example.com"}],
        "source": "openai_web_search",
    }
    fake_client.responses.create.assert_awaited_once()
    kwargs = fake_client.responses.create.await_args.kwargs
    assert kwargs["model"] == "gpt-test"
    assert kwargs["tools"] == [{"type": "web_search"}]
    assert kwargs["stream"] is True

