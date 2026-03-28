import httpx
from pydantic import BaseModel, Field
from openai import pydantic_function_tool

from src.sandbox import Sandbox


class FetchFromGithub(BaseModel):
    """Clone a fork of a repository to a local directory,
    or pull the latest changes if already cloned.
    Pass upstream_url to set the `upstream` remote after a fresh clone.
    """

    repo_url: str = Field(description="Fork repository URL to clone (e.g. https://github.com/Nexus-Tela/repo)")
    local_path: str = Field(description="Local filesystem path where the repository should be cloned or already exists")
    branch: str = Field(default="main", description="Branch to checkout (default: main)")
    token: str | None = Field(default=None, description="GitHub personal access token for private repositories")
    upstream_url: str | None = Field(default=None, description="Original (upstream) repository URL to set as the `upstream` remote after a fresh clone (e.g. https://github.com/owner/repo)")


class CreateGithubIssue(BaseModel):
    """Create a GitHub issue. Must be called before opening a pull request —
    every PR must reference at least one issue."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    title: str = Field(description="Issue title")
    body: str = Field(description="Issue description in markdown — explain the problem or feature clearly")
    labels: list[str] = Field(default=[], description="Labels to apply (e.g. ['bug', 'enhancement'])")


class PrToGithub(BaseModel):
    """Push the current local branch to GitHub and open a pull request.
    Requires a GitHub personal access token with repo scope.
    Every PR must close at least one issue — provide the issue numbers in closes_issues."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    title: str = Field(description="Pull request title")
    body: str = Field(description="Pull request description (markdown supported)")
    head: str = Field(description="Branch that contains the changes to be merged. For cross-repo PRs from your fork, use the format `your-github-nickname:<branch>` (e.g. `Nexus-Tela:feature/my-feature`)")
    base: str = Field(default="main", description="Target branch for the PR (default: main)")
    closes_issues: list[int] = Field(description="Issue numbers this PR resolves — at least one required (e.g. [42])")
    local_path: str | None = Field(default=None, description="Local repository path to push from. Uses current working directory when omitted.")
    draft: bool = Field(default=False, description="Open as a draft pull request (default: false)")


FETCH_FROM_GITHUB   = pydantic_function_tool(FetchFromGithub)
CREATE_GITHUB_ISSUE = pydantic_function_tool(CreateGithubIssue)
PR_TO_GITHUB        = pydantic_function_tool(PrToGithub)

GITHUB_TOOL_DEFINITIONS: list = [FETCH_FROM_GITHUB, CREATE_GITHUB_ISSUE, PR_TO_GITHUB]


class GithubToolKit:
    """GitHub/git operations bound to a sandbox container."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def fetch_from_github(
        self,
        repo_url: str,
        local_path: str,
        branch: str = "main",
        token: str | None = None,
        upstream_url: str | None = None,
    ) -> dict:
        authenticated_url = repo_url
        # if token and repo_url.startswith("https://"):
        #     authenticated_url = repo_url.replace("https://", f"https://x-access-token:{token}@", 1)

        check = await self._sandbox.run_shell(
            f"test -d {local_path}/.git && echo exists || echo new"
        )
        if "exists" in check.get("stdout", ""):
            result = await self._sandbox.run_shell(
                f"git -C {local_path} fetch --all && "
                f"git -C {local_path} checkout {branch} && "
                f"git -C {local_path} pull origin {branch}"
            )
            message = f"Pulled latest on branch '{branch}' at {local_path}"
        else:
            result = await self._sandbox.run_shell(
                f"git clone --branch {branch} {authenticated_url} {local_path}"
            )
            if result.get("success", False) and upstream_url:
                await self._sandbox.run_shell(
                    f"git -C {local_path} remote add upstream {upstream_url} 2>/dev/null || "
                    f"git -C {local_path} remote set-url upstream {upstream_url}"
                )
            message = f"Cloned '{repo_url}' (branch: {branch}) into {local_path}"

        if not result.get("success", False):
            return {
                "success": False,
                "path": local_path,
                "branch": branch,
                "message": result.get("stderr", "git command failed"),
            }
        return {"success": True, "path": local_path, "branch": branch, "message": message}

    async def create_github_issue(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"title": title, "body": body, "labels": labels or []},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "issue_number": data["number"],
                    "issue_url": data["html_url"],
                    "message": f"Issue #{data['number']} created: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "issue_number": None,
                    "issue_url": "",
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }

    async def pr_to_github(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        closes_issues: list[int] | None = None,
        local_path: str | None = None,
        draft: bool = False,
    ) -> dict:
        if closes_issues:
            body = body + "\n\n" + "\n".join(f"Closes #{n}" for n in closes_issues)

        push_cmd = (
            f"git -C {local_path} push origin {head}"
            if local_path
            else f"git push origin {head}"
        )
        result = await self._sandbox.run_shell(push_cmd)
        if not result.get("success", False):
            return {
                "success": False,
                "pr_url": "",
                "pr_number": None,
                "message": f"Failed to push branch '{head}': {result.get('stderr', '')}",
            }

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
                data = response.json()
                return {
                    "success": True,
                    "pr_url": data["html_url"],
                    "pr_number": data["number"],
                    "message": f"Pull request #{data['number']} created: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "pr_url": "",
                    "pr_number": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }



