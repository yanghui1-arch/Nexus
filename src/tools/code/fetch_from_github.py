import asyncio
import os
from pathlib import Path
from pydantic import BaseModel, Field
from openai import pydantic_function_tool


class FetchFromGithub(BaseModel):
    """Clone a GitHub repository to a local directory
    or pull the latest changes if already cloned.
    Supports private repos via a personal access token.
    """

    repo_url: str = Field(description="GitHub repository URL (e.g. https://github.com/owner/repo)")
    local_path: str = Field(description="Local filesystem path where the repository should be cloned or already exists")
    branch: str = Field(default="main", description="Branch to checkout (default: main)")
    token: str | None = Field(default=None, description="GitHub personal access token for private repositories")


TOOL_DEFINITION = pydantic_function_tool(FetchFromGithub)


async def _git(*args: str, cwd: Path) -> tuple[int, str]:
    """Run a git command asynchronously, returning (returncode, stderr)."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()
    return proc.returncode, (stderr_bytes.decode().strip() if stderr_bytes else "")


async def fetch_from_github(
    repo_url: str,
    local_path: str,
    branch: str = "main",
    token: str | None = None,
) -> dict:
    """Clone a GitHub repo or pull the latest changes to a local path."""
    path = Path(local_path).resolve()

    authenticated_url = repo_url
    if token and repo_url.startswith("https://"):
        authenticated_url = repo_url.replace("https://", f"https://{token}@", 1)

    try:
        if (path / ".git").exists():
            for args in (
                ("fetch", "--all"),
                ("checkout", branch),
                ("pull", "origin", branch),
            ):
                code, stderr = await _git(*args, cwd=path)
                if code != 0:
                    return {"success": False, "path": str(path), "branch": branch, "message": f"Git error: {stderr}"}
            message = f"Pulled latest changes on branch '{branch}' in {path}"
        else:
            path.mkdir(parents=True, exist_ok=True)
            code, stderr = await _git("clone", "--branch", branch, authenticated_url, str(path), cwd=path.parent)
            if code != 0:
                return {"success": False, "path": str(path), "branch": branch, "message": f"Git error: {stderr}"}
            message = f"Cloned '{repo_url}' (branch: {branch}) into {path}"

        return {"success": True, "path": str(path), "branch": branch, "message": message}

    except OSError as e:
        return {"success": False, "path": str(path), "branch": branch, "message": str(e)}
