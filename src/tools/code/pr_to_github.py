import asyncio
import os
from pathlib import Path
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
import httpx


class PrToGithub(BaseModel):
    """Push the current local branch to GitHub and open a pull request.
    Requires a GitHub personal access token with repo scope."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    title: str = Field(description="Pull request title")
    body: str = Field(description="Pull request description (markdown supported)")
    head: str = Field(description="Branch that contains the changes to be merged")
    base: str = Field(default="main", description="Target branch for the PR (default: main)")
    local_path: str | None = Field(default=None, description="Local repository path to push from. Uses current working directory when omitted.")
    draft: bool = Field(default=False, description="Open as a draft pull request (default: false)")


TOOL_DEFINITION = pydantic_function_tool(PrToGithub)


async def pr_to_github(
    token: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str = "main",
    local_path: str | None = None,
    draft: bool = False,
) -> dict:
    """Push the current branch and open a pull request on GitHub."""
    work_dir = Path(local_path).resolve() if local_path else Path.cwd()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    # Push the branch to origin
    proc = await asyncio.create_subprocess_exec(
        "git", "push", "origin", head,
        cwd=work_dir,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()
    if proc.returncode != 0:
        stderr = stderr_bytes.decode().strip() if stderr_bytes else ""
        return {"success": False, "pr_url": "", "pr_number": None, "message": f"Failed to push branch '{head}': {stderr}"}

    # Create the pull request via GitHub REST API
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "pr_url": result["html_url"],
                "pr_number": result["number"],
                "message": f"Pull request #{result['number']} created: {result['html_url']}",
            }
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("message", e.response.text)
            return {"success": False, "pr_url": "", "pr_number": None, "message": f"GitHub API error {e.response.status_code}: {error_detail}"}
