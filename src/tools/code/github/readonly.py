from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal

import httpx
from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field


_GITHUB_API = "https://api.github.com"


class ListGithubIssues(BaseModel):
    """List GitHub issues with summary information without modifying GitHub."""

    repo: str | None = Field(default=None, description="Optional owner/repo. Defaults to Marc's repository context.")
    repo_url: str | None = Field(default=None, description="Optional GitHub repository URL or owner/repo")
    state: Literal["open", "closed", "all"] = Field(default="open", description="Issue state to list")
    labels: list[str] = Field(default_factory=list, description="Optional labels to filter by")
    assignee: str | None = Field(default=None, description="Optional assignee login")
    creator: str | None = Field(default=None, description="Optional creator login")
    mentioned: str | None = Field(default=None, description="Optional mentioned user login")
    since: str | None = Field(default=None, description="Optional ISO timestamp; only issues updated after this time")
    per_page: int = Field(default=30, description="Maximum issues to return")


class GetGithubIssue(BaseModel):
    """Get a GitHub issue body and conversation without modifying GitHub."""

    issue_number: int = Field(description="GitHub issue number")
    repo: str | None = Field(default=None, description="Optional owner/repo. Defaults to Marc's repository context.")
    repo_url: str | None = Field(default=None, description="Optional GitHub repository URL or owner/repo")
    include_comments: bool = Field(default=True, description="Whether to include issue comments")
    per_page: int = Field(default=100, description="Maximum comments per page")


class ListGithubPullRequests(BaseModel):
    """List GitHub pull requests with summary information without modifying GitHub."""

    repo: str | None = Field(default=None, description="Optional owner/repo. Defaults to Marc's repository context.")
    repo_url: str | None = Field(default=None, description="Optional GitHub repository URL or owner/repo")
    state: Literal["open", "closed", "all"] = Field(default="open", description="Pull request state to list")
    head: str | None = Field(default=None, description="Optional head user/org and branch filter")
    base: str | None = Field(default=None, description="Optional base branch filter")
    sort: Literal["created", "updated", "popularity", "long-running"] = Field(default="updated", description="Sort field")
    direction: Literal["asc", "desc"] = Field(default="desc", description="Sort direction")
    per_page: int = Field(default=30, description="Maximum pull requests to return")


class GetGithubPullRequest(BaseModel):
    """Get a GitHub pull request body, conversation, review context, files, commits, and checks without modifying GitHub."""

    pull_number: int = Field(description="GitHub pull request number")
    repo: str | None = Field(default=None, description="Optional owner/repo. Defaults to Marc's repository context.")
    repo_url: str | None = Field(default=None, description="Optional GitHub repository URL or owner/repo")
    include_comments: bool = Field(default=True, description="Whether to include PR conversation comments")
    include_reviews: bool = Field(default=True, description="Whether to include PR reviews")
    include_review_comments: bool = Field(default=True, description="Whether to include inline review comments")
    include_files: bool = Field(default=True, description="Whether to include changed files")
    include_commits: bool = Field(default=True, description="Whether to include commits")
    include_checks: bool = Field(default=True, description="Whether to include check runs and commit statuses")
    per_page: int = Field(default=100, description="Maximum items per page for nested lists")


LIST_GITHUB_ISSUES = pydantic_function_tool(ListGithubIssues)
GET_GITHUB_ISSUE = pydantic_function_tool(GetGithubIssue)
LIST_GITHUB_PULL_REQUESTS = pydantic_function_tool(ListGithubPullRequests)
GET_GITHUB_PULL_REQUEST = pydantic_function_tool(GetGithubPullRequest)
GITHUB_READONLY_TOOL_DEFINITIONS = [
    LIST_GITHUB_ISSUES,
    GET_GITHUB_ISSUE,
    LIST_GITHUB_PULL_REQUESTS,
    GET_GITHUB_PULL_REQUEST,
]


class GithubReadOnlyTools:
    def __init__(
        self,
        *,
        default_repo: str | None = None,
        default_repo_url: str | None = None,
        token: str | None = None,
    ) -> None:
        """Initialize the object."""
        self.default_repo = _parse_github_repo(default_repo) or _parse_github_repo(default_repo_url)
        if not token:
            raise ValueError("GitHub token is required for GithubReadOnlyTools.")
        self.token = token

    @property
    def all_tools(self) -> dict[str, Callable]:
        """Return all tools exposed by this toolkit."""
        return {
            "ListGithubIssues": self.list_github_issues,
            "GetGithubIssue": self.get_github_issue,
            "ListGithubPullRequests": self.list_github_pull_requests,
            "GetGithubPullRequest": self.get_github_pull_request,
        }

    @track(step_type="tool")
    async def list_github_issues(
        self,
        repo: str | None = None,
        repo_url: str | None = None,
        state: str = "open",
        labels: list[str] | None = None,
        assignee: str | None = None,
        creator: str | None = None,
        mentioned: str | None = None,
        since: str | None = None,
        per_page: int = 30,
    ) -> dict[str, Any]:
        """List GitHub issues."""
        resolved = self._resolve_repo(repo, repo_url)
        if not resolved["success"]:
            return resolved
        params = {
            "state": state,
            "per_page": _clamp(per_page, 1, 100),
        }
        if labels:
            params["labels"] = ",".join(labels)
        if assignee:
            params["assignee"] = assignee
        if creator:
            params["creator"] = creator
        if mentioned:
            params["mentioned"] = mentioned
        if since:
            params["since"] = since
        data = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/issues", params=params)
        if not data["success"]:
            return data
        issues = [_summarize_issue(item) for item in data["data"] if "pull_request" not in item]
        return {"success": True, "repo": resolved["repo"], "issues": issues, "count": len(issues)}

    @track(step_type="tool")
    async def get_github_issue(
        self,
        issue_number: int,
        repo: str | None = None,
        repo_url: str | None = None,
        include_comments: bool = True,
        per_page: int = 100,
    ) -> dict[str, Any]:
        """Fetch a GitHub issue."""
        resolved = self._resolve_repo(repo, repo_url)
        if not resolved["success"]:
            return resolved
        issue = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/issues/{issue_number}")
        if not issue["success"]:
            return issue
        result = {
            "success": True,
            "repo": resolved["repo"],
            "issue": _format_issue(issue["data"]),
            "comments": [],
        }
        if include_comments:
            comments = await self._get_paginated(
                f"{_GITHUB_API}/repos/{resolved['repo']}/issues/{issue_number}/comments",
                params={"per_page": _clamp(per_page, 1, 100)},
            )
            if comments["success"]:
                result["comments"] = [_format_comment(item) for item in comments["data"]]
                result["comment_count"] = len(result["comments"])
            else:
                result["comments_error"] = comments["message"]
        return result

    @track(step_type="tool")
    async def list_github_pull_requests(
        self,
        repo: str | None = None,
        repo_url: str | None = None,
        state: str = "open",
        head: str | None = None,
        base: str | None = None,
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
    ) -> dict[str, Any]:
        """List GitHub pull requests."""
        resolved = self._resolve_repo(repo, repo_url)
        if not resolved["success"]:
            return resolved
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": _clamp(per_page, 1, 100),
        }
        if head:
            params["head"] = head
        if base:
            params["base"] = base
        data = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/pulls", params=params)
        if not data["success"]:
            return data
        pulls = [_summarize_pull_request(item) for item in data["data"]]
        return {"success": True, "repo": resolved["repo"], "pull_requests": pulls, "count": len(pulls)}

    @track(step_type="tool")
    async def get_github_pull_request(
        self,
        pull_number: int,
        repo: str | None = None,
        repo_url: str | None = None,
        include_comments: bool = True,
        include_reviews: bool = True,
        include_review_comments: bool = True,
        include_files: bool = True,
        include_commits: bool = True,
        include_checks: bool = True,
        per_page: int = 100,
    ) -> dict[str, Any]:
        """Fetch a GitHub pull request."""
        resolved = self._resolve_repo(repo, repo_url)
        if not resolved["success"]:
            return resolved
        pull = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/pulls/{pull_number}")
        if not pull["success"]:
            return pull
        result: dict[str, Any] = {
            "success": True,
            "repo": resolved["repo"],
            "pull_request": _format_pull_request(pull["data"]),
            "comments": [],
            "reviews": [],
            "review_comments": [],
            "files": [],
            "commits": [],
            "checks": {"check_runs": [], "statuses": []},
        }
        page_size = _clamp(per_page, 1, 100)
        if include_comments:
            await self._attach_list(result, "comments", f"{_GITHUB_API}/repos/{resolved['repo']}/issues/{pull_number}/comments", _format_comment, page_size)
        if include_reviews:
            await self._attach_list(result, "reviews", f"{_GITHUB_API}/repos/{resolved['repo']}/pulls/{pull_number}/reviews", _format_review, page_size)
        if include_review_comments:
            await self._attach_list(result, "review_comments", f"{_GITHUB_API}/repos/{resolved['repo']}/pulls/{pull_number}/comments", _format_review_comment, page_size)
        if include_files:
            await self._attach_list(result, "files", f"{_GITHUB_API}/repos/{resolved['repo']}/pulls/{pull_number}/files", _format_changed_file, page_size)
        if include_commits:
            await self._attach_list(result, "commits", f"{_GITHUB_API}/repos/{resolved['repo']}/pulls/{pull_number}/commits", _format_commit, page_size)
        if include_checks:
            sha = pull["data"].get("head", {}).get("sha")
            if sha:
                check_runs = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/commits/{sha}/check-runs")
                statuses = await self._get(f"{_GITHUB_API}/repos/{resolved['repo']}/commits/{sha}/statuses")
                result["checks"] = {
                    "available": check_runs["success"] or statuses["success"],
                    "check_runs": [_format_check_run(item) for item in check_runs.get("data", {}).get("check_runs", [])] if check_runs["success"] else [],
                    "statuses": [_format_status(item) for item in statuses.get("data", [])] if statuses["success"] else [],
                    "errors": [item["message"] for item in (check_runs, statuses) if not item["success"]],
                }
        return result

    async def _attach_list(
        self,
        result: dict[str, Any],
        key: str,
        url: str,
        formatter: Callable[[dict[str, Any]], dict[str, Any]],
        per_page: int,
    ) -> None:
        """Attach a list to a result when populated."""
        data = await self._get_paginated(url, params={"per_page": per_page})
        if data["success"]:
            result[key] = [formatter(item) for item in data["data"]]
            result[f"{key}_count"] = len(result[key])
        else:
            result[f"{key}_error"] = data["message"]

    async def _get_paginated(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch paginated GitHub API results."""
        page = 1
        max_pages = 3
        collected: list[dict[str, Any]] = []
        while page <= max_pages:
            request_params = dict(params or {})
            request_params["page"] = page
            data = await self._get(url, params=request_params)
            if not data["success"]:
                return data
            batch = data["data"]
            if not isinstance(batch, list):
                return {"success": True, "data": collected}
            collected.extend(batch)
            per_page = int(request_params.get("per_page", 100))
            if len(batch) < per_page:
                return {"success": True, "data": collected}
            page += 1
        return {"success": True, "data": collected, "truncated": True}

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch one GitHub API endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=_github_headers(self.token), params=params)
                response.raise_for_status()
                return {"success": True, "data": response.json()}
        except httpx.HTTPStatusError as exc:
            return {"success": False, "message": _github_error_message(exc), "data": None}
        except Exception as exc:
            return {"success": False, "message": str(exc), "data": None}

    def _resolve_repo(self, repo: str | None, repo_url: str | None) -> dict[str, Any]:
        """Resolve the repository for a GitHub request."""
        resolved = _parse_github_repo(repo) or _parse_github_repo(repo_url) or self.default_repo
        if not resolved:
            return {"success": False, "message": "GitHub repository is required. Provide repo or repo_url."}
        return {"success": True, "repo": resolved}


def _github_headers(token: str | None) -> dict[str, str]:
    """Build GitHub API headers for a token."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_github_repo(repo_url: str | None) -> str | None:
    """Parse an owner/repo string."""
    if not repo_url:
        return None
    value = repo_url.strip()
    if not value:
        return None
    if value.startswith("git@github.com:"):
        value = value.removeprefix("git@github.com:")
    elif "github.com/" in value:
        value = value.split("github.com/", 1)[1]
    value = value.removesuffix(".git").strip("/")
    parts = value.split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return f"{parts[0]}/{parts[1]}"
    return None


def _summarize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Build a compact issue summary."""
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "labels": [label.get("name") for label in issue.get("labels", [])],
        "author": issue.get("user", {}).get("login"),
        "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])],
        "comments": issue.get("comments", 0),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "html_url": issue.get("html_url"),
        "body_preview": _preview(issue.get("body")),
    }


def _format_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Format an issue for display."""
    summary = _summarize_issue(issue)
    summary["body"] = issue.get("body") or ""
    return summary


def _summarize_pull_request(pr: dict[str, Any]) -> dict[str, Any]:
    """Build a compact pull request summary."""
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "draft": pr.get("draft"),
        "author": pr.get("user", {}).get("login"),
        "base": pr.get("base", {}).get("ref"),
        "head": pr.get("head", {}).get("ref"),
        "head_sha": pr.get("head", {}).get("sha"),
        "comments": pr.get("comments"),
        "review_comments": pr.get("review_comments"),
        "commits": pr.get("commits"),
        "changed_files": pr.get("changed_files"),
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
        "html_url": pr.get("html_url"),
        "body_preview": _preview(pr.get("body")),
    }


def _format_pull_request(pr: dict[str, Any]) -> dict[str, Any]:
    """Format a pull request for display."""
    summary = _summarize_pull_request(pr)
    summary["body"] = pr.get("body") or ""
    summary["mergeable"] = pr.get("mergeable")
    summary["merged"] = pr.get("merged")
    return summary


def _format_comment(comment: dict[str, Any]) -> dict[str, Any]:
    """Format a GitHub comment for display."""
    return {
        "id": comment.get("id"),
        "author": comment.get("user", {}).get("login"),
        "body": comment.get("body") or "",
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "html_url": comment.get("html_url"),
    }


def _format_review(review: dict[str, Any]) -> dict[str, Any]:
    """Format a pull request review for display."""
    return {
        "id": review.get("id"),
        "author": review.get("user", {}).get("login"),
        "state": review.get("state"),
        "body": review.get("body") or "",
        "submitted_at": review.get("submitted_at"),
        "html_url": review.get("html_url"),
    }


def _format_review_comment(comment: dict[str, Any]) -> dict[str, Any]:
    """Format a review comment for display."""
    return {
        "id": comment.get("id"),
        "author": comment.get("user", {}).get("login"),
        "body": comment.get("body") or "",
        "path": comment.get("path"),
        "line": comment.get("line"),
        "original_line": comment.get("original_line"),
        "commit_id": comment.get("commit_id"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "html_url": comment.get("html_url"),
    }


def _format_changed_file(file: dict[str, Any]) -> dict[str, Any]:
    """Format a changed file entry."""
    return {
        "filename": file.get("filename"),
        "status": file.get("status"),
        "additions": file.get("additions"),
        "deletions": file.get("deletions"),
        "changes": file.get("changes"),
        "patch": file.get("patch"),
    }


def _format_commit(commit: dict[str, Any]) -> dict[str, Any]:
    """Format a commit entry."""
    inner = commit.get("commit", {})
    return {
        "sha": commit.get("sha"),
        "author": inner.get("author", {}).get("name"),
        "message": inner.get("message"),
        "html_url": commit.get("html_url"),
    }


def _format_check_run(check: dict[str, Any]) -> dict[str, Any]:
    """Format a check run entry."""
    return {
        "name": check.get("name"),
        "status": check.get("status"),
        "conclusion": check.get("conclusion"),
        "started_at": check.get("started_at"),
        "completed_at": check.get("completed_at"),
        "html_url": check.get("html_url"),
    }


def _format_status(status: dict[str, Any]) -> dict[str, Any]:
    """Format a commit status entry."""
    return {
        "context": status.get("context"),
        "state": status.get("state"),
        "description": status.get("description"),
        "target_url": status.get("target_url"),
        "created_at": status.get("created_at"),
        "updated_at": status.get("updated_at"),
    }


def _preview(text: str | None, limit: int = 300) -> str:
    """Return a shortened text preview."""
    value = (text or "").strip()
    return value[:limit]


def _github_error_message(exc: httpx.HTTPStatusError) -> str:
    """Extract a readable GitHub error message."""
    try:
        detail = exc.response.json().get("message", exc.response.text)
    except Exception:
        detail = exc.response.text

    detail_text = detail if isinstance(detail, str) else str(detail)
    remaining = exc.response.headers.get("x-ratelimit-remaining")
    if exc.response.status_code in {403, 429} and (
        remaining == "0" or "rate limit" in detail_text.lower()
    ):
        message = f"GitHub API rate limit exceeded: {detail_text}"
        reset = exc.response.headers.get("x-ratelimit-reset")
        if reset is not None:
            try:
                reset_at = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()
                message += f" Rate limit resets at {reset_at}."
            except ValueError:
                pass
        return message
    return f"GitHub API error {exc.response.status_code}: {detail_text}"


def _clamp(value: int, lower: int, upper: int) -> int:
    """Clamp a numeric value between bounds."""
    return max(lower, min(value, upper))
