from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .types import ChangedFile, CheckSummary, PullRequestContext, PullRequestSummary


GITHUB_API_BASE_URL = "https://api.github.com"


class GithubSecretaryError(RuntimeError):
    """Raised when a GitHub secretary operation fails."""


class GithubSecretaryClient:
    """GitHub REST client for secretary review and merge operations."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_API_BASE_URL,
        timeout: float = 15.0,
    ) -> None:
        """Initialize the client."""
        if not token:
            raise ValueError("GitHub token is required.")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._viewer_login: str | None = None

    async def viewer_login(self) -> str | None:
        """Return the authenticated GitHub login."""
        if self._viewer_login is not None:
            return self._viewer_login
        payload = await self._request("GET", "/user")
        login = payload.get("login") if isinstance(payload, dict) else None
        self._viewer_login = login.strip() if isinstance(login, str) and login.strip() else None
        return self._viewer_login

    async def list_open_pull_requests(self, repo: str) -> list[PullRequestSummary]:
        """List open pull requests for a repository."""
        payload = await self._get_paginated(f"/repos/{repo}/pulls", params={"state": "open", "per_page": 100})
        return [_format_pull_summary(repo, item) for item in payload]

    async def get_pull_request_context(self, repo: str, pull_number: int) -> PullRequestContext:
        """Fetch the review context for one pull request."""
        pull = await self._request("GET", f"/repos/{repo}/pulls/{pull_number}")
        files = await self._get_paginated(f"/repos/{repo}/pulls/{pull_number}/files", params={"per_page": 100})
        reviews = await self._get_paginated(f"/repos/{repo}/pulls/{pull_number}/reviews", params={"per_page": 100})
        comments = await self._get_paginated(f"/repos/{repo}/issues/{pull_number}/comments", params={"per_page": 100})
        review_comments = await self._get_paginated(f"/repos/{repo}/pulls/{pull_number}/comments", params={"per_page": 100})
        head_sha = pull.get("head", {}).get("sha")
        check_runs: list[dict[str, Any]] = []
        statuses: list[dict[str, Any]] = []
        if head_sha:
            check_payload = await self._request("GET", f"/repos/{repo}/commits/{head_sha}/check-runs")
            check_runs = list(check_payload.get("check_runs", [])) if isinstance(check_payload, dict) else []
            statuses_payload = await self._request("GET", f"/repos/{repo}/commits/{head_sha}/statuses")
            statuses = statuses_payload if isinstance(statuses_payload, list) else []
        return PullRequestContext(
            summary=_format_pull_summary(repo, pull),
            body=pull.get("body") or "",
            files=[_format_file(item) for item in files],
            reviews=reviews,
            comments=comments,
            review_comments=review_comments,
            check_runs=check_runs,
            statuses=statuses,
        )

    async def create_review(
        self,
        repo: str,
        pull_number: int,
        *,
        event: str,
        body: str,
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a formal pull request review."""
        payload: dict[str, Any] = {
            "event": event,
            "body": body,
        }
        if comments:
            payload["comments"] = comments
        result = await self._request(
            "POST",
            f"/repos/{repo}/pulls/{pull_number}/reviews",
            json=payload,
        )
        return result if isinstance(result, dict) else {}

    async def merge_pull_request(
        self,
        repo: str,
        pull_number: int,
        *,
        sha: str,
        merge_method: str,
    ) -> dict[str, Any]:
        """Merge a pull request using an expected head SHA."""
        payload = {
            "sha": sha,
            "merge_method": merge_method,
        }
        result = await self._request(
            "PUT",
            f"/repos/{repo}/pulls/{pull_number}/merge",
            json=payload,
        )
        return result if isinstance(result, dict) else {}

    async def _get_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """Fetch a bounded paginated GitHub list endpoint."""
        page = 1
        items: list[dict[str, Any]] = []
        while page <= max_pages:
            request_params = dict(params or {})
            request_params["page"] = page
            payload = await self._request("GET", path, params=request_params)
            if not isinstance(payload, list):
                return items
            items.extend(payload)
            per_page = int(request_params.get("per_page", 100))
            if len(payload) < per_page:
                return items
            page += 1
        return items

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Perform one GitHub REST request."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=_github_headers(self._token),
                **kwargs,
            )
        if 200 <= response.status_code < 300:
            if not response.content:
                return {}
            return response.json()
        raise GithubSecretaryError(
            f"GitHub API error {response.status_code}: {_github_error_message(response)}"
        )


def summarize_checks(context: PullRequestContext) -> CheckSummary:
    """Summarize GitHub check-runs and statuses for merge gating."""
    pending: list[str] = []
    failed: list[str] = []
    successful: list[str] = []

    for check in context.check_runs:
        name = str(check.get("name") or "check")
        status = str(check.get("status") or "")
        conclusion = check.get("conclusion")
        if status != "completed":
            pending.append(name)
            continue
        if conclusion in {"success", "neutral", "skipped"}:
            successful.append(name)
        else:
            failed.append(f"{name}:{conclusion or 'unknown'}")

    for status in context.statuses:
        name = str(status.get("context") or "status")
        state = str(status.get("state") or "")
        if state == "success":
            successful.append(name)
        elif state in {"pending", "expected"}:
            pending.append(name)
        else:
            failed.append(f"{name}:{state or 'unknown'}")

    return CheckSummary(
        available=bool(context.check_runs or context.statuses),
        pending=pending,
        failed=failed,
        successful=successful,
    )


def _github_headers(token: str) -> dict[str, str]:
    """Build GitHub REST headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _github_error_message(response: httpx.Response) -> str:
    """Return a readable GitHub error message."""
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            remaining = response.headers.get("x-ratelimit-remaining")
            if response.status_code in {403, 429} and remaining == "0":
                reset = response.headers.get("x-ratelimit-reset")
                if reset:
                    try:
                        reset_at = datetime.fromtimestamp(int(reset), tz=timezone.utc).isoformat()
                        return f"{message}; rate limit resets at {reset_at}"
                    except ValueError:
                        pass
            return message
    return response.text


def _format_pull_summary(repo: str, payload: dict[str, Any]) -> PullRequestSummary:
    """Format GitHub pull payload."""
    head = payload.get("head") or {}
    base = payload.get("base") or {}
    return PullRequestSummary(
        repo=repo,
        number=int(payload.get("number") or 0),
        title=payload.get("title") or "",
        state=payload.get("state") or "",
        draft=bool(payload.get("draft")),
        html_url=payload.get("html_url") or "",
        author=(payload.get("user") or {}).get("login"),
        head_sha=head.get("sha") or "",
        head_ref=head.get("ref") or "",
        base_ref=base.get("ref") or "",
        mergeable=payload.get("mergeable"),
        mergeable_state=payload.get("mergeable_state"),
    )


def _format_file(payload: dict[str, Any]) -> ChangedFile:
    """Format GitHub changed-file payload."""
    return ChangedFile(
        filename=payload.get("filename") or "",
        status=payload.get("status"),
        additions=int(payload.get("additions") or 0),
        deletions=int(payload.get("deletions") or 0),
        changes=int(payload.get("changes") or 0),
        patch=payload.get("patch"),
    )
