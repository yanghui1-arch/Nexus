from __future__ import annotations

from types import SimpleNamespace

import anyio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools import web_search as web_search_module


class FakeStream:
    def __init__(self, events):
        self._events = events

    def __aiter__(self):
        self._iter = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def test_openai_web_search_stream_collects_answer_and_citations():
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


def test_tool_definition_identifies_web_search_agent():
    assert web_search_module.TOOL_DEFINITION["function"]["name"] == "web_search_agent"
    description = web_search_module.TOOL_DEFINITION["function"]["description"]
    assert "Web search agent" in description
    properties = web_search_module.TOOL_DEFINITION["function"]["parameters"]["properties"]
    assert properties["query"]["description"] == "Research question or web search query for the agent"
    assert properties["max_results"]["description"] == "Maximum number of cited web results the agent should include"
