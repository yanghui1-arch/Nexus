from __future__ import annotations

from typing import Any

from mwin import track
from openai import AsyncOpenAI, pydantic_function_tool
from pydantic import BaseModel, Field

from src.server.config import get_settings


class WebSearch(BaseModel):
    """Search the web using OpenAI's official web_search tool and return the collected answer."""

    query: str = Field(description="Search query string")
    max_results: int = Field(default=5, description="Maximum number of cited search results to ask for")


TOOL_DEFINITION = pydantic_function_tool(WebSearch)


@track(step_type="tool")
async def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    settings = get_settings()
    if not settings.api_key:
        raise RuntimeError("NEXUS_API_KEY is required for WebSearch.")

    client = AsyncOpenAI(base_url=settings.base_url, api_key=settings.api_key)
    answer_parts: list[str] = []
    citations: list[dict[str, Any]] = []
    stream = await client.responses.create(
        model=settings.model,
        input=(
            f"Search the web for this query and answer with concise findings. "
            f"Include at most {max_results} important source citations.\n\nQuery: {query}"
        ),
        tools=[{"type": "web_search"}],
        stream=True,
    )
    async for event in stream:
        event_type = getattr(event, "type", None)
        if event_type == "response.output_text.delta":
            answer_parts.append(getattr(event, "delta", ""))
            continue
        if event_type == "response.output_text.annotation.added":
            annotation = getattr(event, "annotation", None)
            if annotation is not None:
                citations.append(annotation.model_dump(mode="json", exclude_none=True))

    return {
        "success": True,
        "query": query,
        "answer": "".join(answer_parts).strip(),
        "citations": citations,
        "source": "openai_web_search",
    }
