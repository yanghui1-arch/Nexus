import sys
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
from mcp import StdioServerParameters

from .client import MCPClient


class WebFetch(BaseModel):
    """Fetch the content of a web page and return it as markdown text."""

    url: str = Field(description="URL of the web page to fetch")
    max_length: int = Field(default=5000, description="Maximum number of characters to return")
    start_index: int = Field(default=0, description="Start character index for paginating through large pages")
    raw: bool = Field(default=False, description="Return raw HTML instead of markdown (default: false)")


TOOL_DEFINITION = pydantic_function_tool(WebFetch)

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server_fetch"],
)


async def web_fetch(
    url: str,
    max_length: int = 5000,
    start_index: int = 0,
    raw: bool = False,
) -> dict:
    """Fetch web page content via the mcp-server-fetch MCP server.

    A new MCP session is started per call. For high-frequency use,
    consider managing a shared session at the agent level instead.
    """
    try:
        async with MCPClient(_SERVER_PARAMS) as client:
            result = await client.call_tool(
                "fetch",
                {"url": url, "max_length": max_length, "start_index": start_index, "raw": raw},
            )

        if result.get("isError"):
            return {"success": False, "url": url, "content": "", "message": result.get("content", "Unknown error")}

        content = result.get("content", "")
        if content:
            return {"success": True, "url": url, "content": content}
        return {"success": False, "url": url, "content": "", "message": "No content returned"}

    except Exception as e:
        return {"success": False, "url": url, "content": "", "message": str(e)}
