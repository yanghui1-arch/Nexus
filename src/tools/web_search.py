import asyncio
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
from mwin import track


class WebSearch(BaseModel):
    """Search the web using DuckDuckGo and return a list of results with title, URL, and snippet."""

    query: str = Field(description="Search query string")
    max_results: int = Field(default=5, description="Maximum number of results to return (default: 5)")


TOOL_DEFINITION = pydantic_function_tool(WebSearch)


@track(step_type="tool")
async def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo.

    Returns dict with keys: success, results, error.
    Each result has keys: title, href, body.
    """
    try:
        from duckduckgo_search import DDGS
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(query, max_results=max_results))
        )
        return {"success": True, "results": results, "error": None}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}
