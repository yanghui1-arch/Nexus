"""Tests for GitHub tools including review and comment interaction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.tools.code import GITHUB_TOOLS_SCHEMA, GithubTools
from src.tools.code.github.issue import (
    GET_ISSUE_COMMENTS,
    REPLY_TO_ISSUE,
    GET_MY_ISSUES,
)
from src.tools.code.github.pr import (
    GET_PR_REVIEWS,
    GET_PR_REVIEW_COMMENTS,
    REPLY_TO_PR_REVIEW_COMMENT,
    GET_PR_COMMENTS,
    REPLY_TO_PR,
    GET_MY_OPEN_PRS,
)
from src.tools.code.github.notification import GET_NOTIFICATIONS


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for testing."""
    sandbox = MagicMock()
    sandbox.run_shell = AsyncMock()
    return sandbox


@pytest.fixture
def github_kit(mock_sandbox):
    """Create a GithubTools instance with mock sandbox."""
    return GithubTools(mock_sandbox)


class TestGetIssueComments:
    """Tests for GetIssueComments tool."""

    async def test_get_issue_comments_success(self, github_kit):
        """Test successful retrieval of issue comments."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 123,
                "user": {"login": "testuser"},
                "body": "This is a test comment",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/test/repo/issues/1#issuecomment-123",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_issue_comments(
                token="test-token",
                repo="test/repo",
                issue_number=1,
            )

        assert result["success"] is True
        assert result["issue_number"] == 1
        assert result["comment_count"] == 1
        assert len(result["comments"]) == 1
        assert result["comments"][0]["user"] == "testuser"
        assert result["comments"][0]["body"] == "This is a test comment"

    async def test_get_issue_comments_empty(self, github_kit):
        """Test retrieval of issue with no comments."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_issue_comments(
                token="test-token",
                repo="test/repo",
                issue_number=1,
            )

        assert result["success"] is True
        assert result["comment_count"] == 0
        assert result["comments"] == []

    async def test_get_issue_comments_api_error(self, github_kit):
        """Test handling of API error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "Not Found"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_issue_comments(
                token="test-token",
                repo="test/repo",
                issue_number=999,
            )

        assert result["success"] is False
        assert "comments" in result
        assert "Not Found" in result["message"]


class TestReplyToIssue:
    """Tests for ReplyToIssue tool."""

    async def test_reply_to_issue_success(self, github_kit):
        """Test successful comment creation on issue."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 456,
            "html_url": "https://github.com/test/repo/issues/1#issuecomment-456",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await github_kit.reply_to_issue(
                token="test-token",
                repo="test/repo",
                issue_number=1,
                body="Thank you for the feedback!",
            )

        assert result["success"] is True
        assert result["comment_id"] == 456
        assert "github.com/test/repo/issues/1#issuecomment-456" in result["comment_url"]
        assert "Comment added" in result["message"]


class TestGetPRReviews:
    """Tests for GetPRReviews tool."""

    async def test_get_pr_reviews_success(self, github_kit):
        """Test successful retrieval of PR reviews."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 789,
                "user": {"login": "reviewer"},
                "state": "CHANGES_REQUESTED",
                "body": "Please fix the indentation",
                "submitted_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/test/repo/pull/1#pullrequestreview-789",
            },
            {
                "id": 790,
                "user": {"login": "reviewer2"},
                "state": "APPROVED",
                "body": "LGTM!",
                "submitted_at": "2024-01-02T00:00:00Z",
                "html_url": "https://github.com/test/repo/pull/1#pullrequestreview-790",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_pr_reviews(
                token="test-token",
                repo="test/repo",
                pull_number=1,
            )

        assert result["success"] is True
        assert result["pull_number"] == 1
        assert result["review_count"] == 2
        assert result["reviews"][0]["state"] == "CHANGES_REQUESTED"
        assert result["reviews"][1]["state"] == "APPROVED"


class TestGetPRReviewComments:
    """Tests for GetPRReviewComments tool."""

    async def test_get_pr_review_comments_success(self, github_kit):
        """Test successful retrieval of inline review comments."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 100,
                "user": {"login": "reviewer"},
                "body": "This variable name could be more descriptive",
                "path": "src/main.py",
                "line": 42,
                "original_line": 42,
                "commit_id": "abc123",
                "created_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/test/repo/pull/1#discussion_r100",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_pr_review_comments(
                token="test-token",
                repo="test/repo",
                pull_number=1,
            )

        assert result["success"] is True
        assert result["comment_count"] == 1
        assert result["comments"][0]["path"] == "src/main.py"
        assert result["comments"][0]["line"] == 42


class TestReplyToPRReviewComment:
    """Tests for ReplyToPRReviewComment tool."""

    async def test_reply_to_pr_review_comment_success(self, github_kit):
        """Test successful reply to inline review comment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 200,
            "html_url": "https://github.com/test/repo/pull/1#discussion_r200",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await github_kit.reply_to_pr_review_comment(
                token="test-token",
                repo="test/repo",
                pull_number=1,
                comment_id=100,
                body="Good point! I'll update the variable name.",
            )

        assert result["success"] is True
        assert result["reply_id"] == 200
        assert "Reply added" in result["message"]


class TestGetPRComments:
    """Tests for GetPRComments tool."""

    async def test_get_pr_comments_success(self, github_kit):
        """Test successful retrieval of PR discussion comments."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 300,
                "user": {"login": "contributor"},
                "body": "Great work on this feature!",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/test/repo/pull/1#issuecomment-300",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_pr_comments(
                token="test-token",
                repo="test/repo",
                pull_number=1,
            )

        assert result["success"] is True
        assert result["comment_count"] == 1
        assert result["comments"][0]["body"] == "Great work on this feature!"


class TestGetMyOpenPRs:
    """Tests for GetMyOpenPRs tool."""

    async def test_get_my_open_prs_success(self, github_kit):
        """Test successful retrieval of user's open PRs."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Add new feature",
                "state": "open",
                "html_url": "https://github.com/test/repo/pull/1",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "comments": 5,
                "review_comments": 3,
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_my_open_prs(
                token="test-token",
                repo="test/repo",
                creator="testuser",
            )

        assert result["success"] is True
        assert result["pr_count"] == 1
        assert result["pull_requests"][0]["number"] == 1
        assert result["pull_requests"][0]["comments"] == 5


class TestGetMyIssues:
    """Tests for GetMyIssues tool."""

    async def test_get_my_issues_success(self, github_kit):
        """Test successful retrieval of user's issues."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Bug report",
                "state": "open",
                "html_url": "https://github.com/test/repo/issues/1",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "comments": 2,
            },
            {
                "number": 2,
                "title": "PR that looks like issue",
                "state": "open",
                "html_url": "https://github.com/test/repo/pull/2",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "comments": 0,
                "pull_request": {},  # This should be filtered out
            },
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_my_issues(
                token="test-token",
                repo="test/repo",
                creator="testuser",
            )

        assert result["success"] is True
        # Should filter out PRs, so only 1 issue
        assert result["issue_count"] == 1
        assert result["issues"][0]["number"] == 1


class TestGetNotifications:
    """Tests for GetNotifications tool."""

    async def test_get_notifications_success(self, github_kit):
        """Test successful retrieval of notifications."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "notif-123",
                "reason": "mention",
                "unread": True,
                "updated_at": "2024-01-01T00:00:00Z",
                "subject": {
                    "title": "Review requested",
                    "type": "PullRequest",
                    "url": "https://api.github.com/repos/test/repo/pulls/1",
                },
                "repository": {
                    "full_name": "test/repo",
                },
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_notifications(
                token="test-token",
            )

        assert result["success"] is True
        assert result["notification_count"] == 1
        assert result["notifications"][0]["reason"] == "mention"
        assert result["notifications"][0]["repository"] == "test/repo"

    async def test_get_notifications_filtered(self, github_kit):
        """Test retrieval of participating notifications only."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await github_kit.get_notifications(
                token="test-token",
                participating=True,
            )

        assert result["success"] is True
        assert result["notification_count"] == 0
        # Verify the request was made with participating=true
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["participating"] == "true"


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_all_new_tools_in_definitions(self):
        """Verify all current GitHub tools are in GITHUB_TOOLS_SCHEMA."""
        expected_tools = [
            GET_ISSUE_COMMENTS,
            REPLY_TO_ISSUE,
            GET_PR_REVIEWS,
            GET_PR_REVIEW_COMMENTS,
            REPLY_TO_PR_REVIEW_COMMENT,
            GET_PR_COMMENTS,
            REPLY_TO_PR,
            GET_MY_OPEN_PRS,
            GET_MY_ISSUES,
            GET_NOTIFICATIONS,
        ]
        for tool in expected_tools:
            assert tool in GITHUB_TOOLS_SCHEMA, f"{tool} not found in GITHUB_TOOLS_SCHEMA"

    def test_tool_definitions_have_required_fields(self):
        """Verify tool definitions have required structure."""
        for tool_def in GITHUB_TOOLS_SCHEMA:
            assert "type" in tool_def
            assert "function" in tool_def
            func = tool_def["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
