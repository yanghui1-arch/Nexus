from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import httpx
import pytest

from src.tools.code.github.readonly import GithubReadOnlyTools, _parse_github_repo


def _response(data):
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


def test_parse_github_repo_forms():
    assert _parse_github_repo("owner/repo") == "owner/repo"
    assert _parse_github_repo("https://github.com/owner/repo") == "owner/repo"
    assert _parse_github_repo("https://github.com/owner/repo.git") == "owner/repo"
    assert _parse_github_repo("git@github.com:owner/repo.git") == "owner/repo"


def test_list_github_issues_returns_summaries_and_uses_token():
    tools = GithubReadOnlyTools(default_repo="owner/repo", token="secret-token")
    issue = {
        "number": 1,
        "title": "Bug",
        "state": "open",
        "labels": [{"name": "bug"}],
        "user": {"login": "alice"},
        "assignees": [{"login": "bob"}],
        "comments": 2,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/owner/repo/issues/1",
        "body": "long issue body",
    }
    pull_as_issue = {**issue, "number": 2, "pull_request": {}}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _response([issue, pull_as_issue])
        result = anyio.run(tools.list_github_issues)

    assert result["success"] is True
    assert result["count"] == 1
    assert result["issues"][0]["title"] == "Bug"
    headers = mock_get.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in str(result)


def test_get_github_issue_returns_body_and_comments():
    tools = GithubReadOnlyTools(default_repo="owner/repo", token="secret-token")
    responses = [
        _response({
            "number": 3,
            "title": "Need context",
            "state": "open",
            "labels": [],
            "user": {"login": "alice"},
            "assignees": [],
            "comments": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/3",
            "body": "full body",
        }),
        _response([{
            "id": 10,
            "user": {"login": "bob"},
            "body": "discussion",
            "created_at": "2026-01-01T01:00:00Z",
            "updated_at": "2026-01-01T01:00:00Z",
            "html_url": "https://github.com/owner/repo/issues/3#issuecomment-10",
        }]),
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = responses
        result = anyio.run(tools.get_github_issue, 3)

    assert result["success"] is True
    assert result["issue"]["body"] == "full body"
    assert result["comments"][0]["body"] == "discussion"


def test_get_github_pull_request_returns_full_context_without_mutating_methods():
    tools = GithubReadOnlyTools(default_repo="owner/repo", token="secret-token")
    pull = {
        "number": 5,
        "title": "Improve flow",
        "state": "open",
        "draft": False,
        "user": {"login": "alice"},
        "base": {"ref": "main"},
        "head": {"ref": "feature", "sha": "abc123"},
        "comments": 1,
        "review_comments": 1,
        "commits": 1,
        "changed_files": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/owner/repo/pull/5",
        "body": "full pr body",
        "mergeable": True,
        "merged": False,
    }
    responses = [
        _response(pull),
        _response([{"id": 1, "user": {"login": "bob"}, "body": "comment"}]),
        _response([{"id": 2, "user": {"login": "carol"}, "state": "APPROVED", "body": "lgtm"}]),
        _response([{"id": 3, "user": {"login": "dan"}, "body": "inline", "path": "src/app.py", "line": 4}]),
        _response([{"filename": "src/app.py", "status": "modified", "additions": 2, "deletions": 1, "changes": 3, "patch": "@@"}]),
        _response([{"sha": "abc123", "commit": {"author": {"name": "Alice"}, "message": "update"}, "html_url": "https://github.com/owner/repo/commit/abc123"}]),
        _response({"check_runs": [{"name": "ci", "status": "completed", "conclusion": "success"}]}),
        _response([{"context": "legacy-ci", "state": "success", "description": "ok"}]),
    ]

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put,
        patch("httpx.AsyncClient.patch", new_callable=AsyncMock) as mock_patch,
        patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete,
    ):
        mock_get.side_effect = responses
        result = anyio.run(tools.get_github_pull_request, 5)

    assert result["success"] is True
    assert result["pull_request"]["body"] == "full pr body"
    assert result["comments"][0]["body"] == "comment"
    assert result["reviews"][0]["state"] == "APPROVED"
    assert result["review_comments"][0]["path"] == "src/app.py"
    assert result["files"][0]["filename"] == "src/app.py"
    assert result["commits"][0]["sha"] == "abc123"
    assert result["checks"]["check_runs"][0]["name"] == "ci"
    assert result["checks"]["statuses"][0]["context"] == "legacy-ci"
    mock_post.assert_not_called()
    mock_put.assert_not_called()
    mock_patch.assert_not_called()
    mock_delete.assert_not_called()


def test_list_github_pull_requests_returns_summaries():
    tools = GithubReadOnlyTools(default_repo="owner/repo", token="secret-token")
    pull = {
        "number": 7,
        "title": "Feature",
        "state": "open",
        "draft": False,
        "user": {"login": "alice"},
        "base": {"ref": "main"},
        "head": {"ref": "feature", "sha": "abc123"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/owner/repo/pull/7",
        "body": "summary body",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _response([pull])
        result = anyio.run(tools.list_github_pull_requests)

    assert result["success"] is True
    assert result["pull_requests"][0]["number"] == 7
    assert result["pull_requests"][0]["body_preview"] == "summary body"


def test_github_readonly_tools_requires_token():
    with pytest.raises(ValueError, match="GitHub token is required"):
        GithubReadOnlyTools(default_repo="owner/repo")


def test_list_github_issues_surfaces_rate_limit_message():
    tools = GithubReadOnlyTools(default_repo="owner/repo", token="secret-token")
    response = httpx.Response(
        403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "4102444800",
        },
        json={"message": "API rate limit exceeded for user."},
        request=httpx.Request("GET", "https://api.github.com/repos/owner/repo/issues"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = anyio.run(tools.list_github_issues)

    assert result["success"] is False
    assert "GitHub API rate limit exceeded" in result["message"]
    assert "Rate limit resets at 2100-01-01" in result["message"]
