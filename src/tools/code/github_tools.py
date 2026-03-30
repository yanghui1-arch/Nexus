import httpx
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
from mwin import track, StepType

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


# =============================================================================
# GitHub Review and Comment Interaction Tools
# =============================================================================


class GetIssueComments(BaseModel):
    """Fetch all comments on a specific GitHub issue. Useful for reading
    feedback and discussions on issues you've created or are working on."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    issue_number: int = Field(description="Issue number to fetch comments for")
    per_page: int = Field(default=30, description="Number of comments per page (default: 30, max: 100)")


class ReplyToIssue(BaseModel):
    """Add a comment to a GitHub issue. Use this to respond to feedback,
    provide updates, or participate in issue discussions."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    issue_number: int = Field(description="Issue number to comment on")
    body: str = Field(description="Comment body in markdown format")


class GetPRReviews(BaseModel):
    """Fetch all reviews on a specific pull request. Reviews include
    approval status (APPROVED, CHANGES_REQUESTED, COMMENTED) and review body."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch reviews for")


class GetPRReviewComments(BaseModel):
    """Fetch inline review comments on a pull request. These are the
    line-specific comments made during code review, separate from general PR comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch review comments for")


class ReplyToPRReviewComment(BaseModel):
    """Reply to a specific inline review comment on a pull request.
    Use this to respond to line-specific feedback during code review."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number")
    comment_id: int = Field(description="ID of the review comment to reply to")
    body: str = Field(description="Reply body in markdown format")


class GetPRComments(BaseModel):
    """Fetch general (non-review) comments on a pull request.
    These are the discussion comments, not inline code review comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch comments for")


class ReplyToPR(BaseModel):
    """Add a general comment to a pull request discussion.
    Use this to respond to general PR feedback or provide updates."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to comment on")
    body: str = Field(description="Comment body in markdown format")


class GetMyOpenPRs(BaseModel):
    """List open pull requests created by you in a repository.
    Useful for checking status of your PRs and finding new comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    creator: str = Field(description="GitHub username to filter PRs by (your username)")
    per_page: int = Field(default=10, description="Number of PRs to fetch (default: 10)")


class GetMyIssues(BaseModel):
    """List issues created by you in a repository.
    Useful for tracking issues you've opened and checking for new comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    creator: str = Field(description="GitHub username to filter issues by (your username)")
    state: str = Field(default="open", description="Issue state: open, closed, or all (default: open)")
    per_page: int = Field(default=10, description="Number of issues to fetch (default: 10)")


class GetNotifications(BaseModel):
    """Fetch GitHub notifications for repositories you participate in.
    Useful for discovering new activity on your PRs, issues, and mentions."""

    token: str = Field(description="GitHub personal access token with repo scope")
    all: bool = Field(default=False, description="If true, show all notifications including read ones (default: false - only unread)")
    participating: bool = Field(default=False, description="If true, only show notifications where you are directly participating (default: false)")
    per_page: int = Field(default=30, description="Number of notifications to fetch (default: 30)")


FETCH_FROM_GITHUB   = pydantic_function_tool(FetchFromGithub)
CREATE_GITHUB_ISSUE = pydantic_function_tool(CreateGithubIssue)
PR_TO_GITHUB        = pydantic_function_tool(PrToGithub)

# New review and comment tools
GET_ISSUE_COMMENTS = pydantic_function_tool(GetIssueComments)
REPLY_TO_ISSUE = pydantic_function_tool(ReplyToIssue)
GET_PR_REVIEWS = pydantic_function_tool(GetPRReviews)
GET_PR_REVIEW_COMMENTS = pydantic_function_tool(GetPRReviewComments)
REPLY_TO_PR_REVIEW_COMMENT = pydantic_function_tool(ReplyToPRReviewComment)
GET_PR_COMMENTS = pydantic_function_tool(GetPRComments)
REPLY_TO_PR = pydantic_function_tool(ReplyToPR)
GET_MY_OPEN_PRS = pydantic_function_tool(GetMyOpenPRs)
GET_MY_ISSUES = pydantic_function_tool(GetMyIssues)
GET_NOTIFICATIONS = pydantic_function_tool(GetNotifications)

GITHUB_TOOL_DEFINITIONS: list = [
    FETCH_FROM_GITHUB,
    CREATE_GITHUB_ISSUE,
    PR_TO_GITHUB,
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


class GithubToolKit:
    """GitHub/git operations bound to a sandbox container."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    @track(step_type=StepType.TOOL)
    async def fetch_from_github(
        self,
        repo_url: str,
        local_path: str,
        branch: str = "main",
        token: str | None = None,
        upstream_url: str | None = None,
    ) -> dict:
        """Fetch from github
        repo_url should always be authenticated_url if github_token is provided.
        """
        
        authenticated_url = repo_url
        if token and repo_url.startswith("https://"):
            authenticated_url = repo_url.replace("https://", f"https://x-access-token:{token}@", 1)

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


    @track(step_type=StepType.TOOL)
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


    @track(step_type=StepType.TOOL)
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

    # ==========================================================================
    # Issue and PR Comment/Review Interaction Methods
    # ==========================================================================

    @track(step_type=StepType.TOOL)
    async def get_issue_comments(
        self,
        token: str,
        repo: str,
        issue_number: int,
        per_page: int = 30,
    ) -> dict:
        """Fetch all comments on a specific issue."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": per_page},
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "issue_number": issue_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} comments on issue #{issue_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def reply_to_issue(
        self,
        token: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        """Add a comment to an issue."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"body": body},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "comment_id": data["id"],
                    "comment_url": data["html_url"],
                    "message": f"Comment added to issue #{issue_number}: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comment_id": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def get_pr_reviews(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch all reviews on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/reviews",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                reviews = response.json()
                formatted_reviews = []
                for review in reviews:
                    formatted_reviews.append({
                        "id": review["id"],
                        "user": review["user"]["login"],
                        "state": review["state"],
                        "body": review["body"],
                        "submitted_at": review.get("submitted_at"),
                        "html_url": review["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "review_count": len(formatted_reviews),
                    "reviews": formatted_reviews,
                    "message": f"Retrieved {len(formatted_reviews)} reviews on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "reviews": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def get_pr_review_comments(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch inline review comments on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "path": comment["path"],
                        "line": comment.get("line"),
                        "original_line": comment.get("original_line"),
                        "commit_id": comment["commit_id"],
                        "created_at": comment["created_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} review comments on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def reply_to_pr_review_comment(
        self,
        token: str,
        repo: str,
        pull_number: int,
        comment_id: int,
        body: str,
    ) -> dict:
        """Reply to a specific inline review comment on a PR.
        
        Note: GitHub API creates a reply as a new comment in reply-to relation.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments/{comment_id}/replies",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"body": body},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "reply_id": data["id"],
                    "reply_url": data["html_url"],
                    "message": f"Reply added to review comment: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "reply_id": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def get_pr_comments(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch general (non-review) comments on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                # PR comments are accessed via the issues endpoint
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{pull_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} comments on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def reply_to_pr(
        self,
        token: str,
        repo: str,
        pull_number: int,
        body: str,
    ) -> dict:
        """Add a general comment to a pull request."""
        # PR comments use the same endpoint as issue comments
        return await self.reply_to_issue(token, repo, pull_number, body)


    @track(step_type=StepType.TOOL)
    async def get_my_open_prs(
        self,
        token: str,
        repo: str,
        creator: str,
        per_page: int = 10,
    ) -> dict:
        """List open pull requests created by a specific user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "state": "open",
                        "creator": creator,
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                prs = response.json()
                formatted_prs = []
                for pr in prs:
                    formatted_prs.append({
                        "number": pr["number"],
                        "title": pr["title"],
                        "state": pr["state"],
                        "html_url": pr["html_url"],
                        "created_at": pr["created_at"],
                        "updated_at": pr["updated_at"],
                        "comments": pr["comments"],
                        "review_comments": pr["review_comments"],
                    })
                return {
                    "success": True,
                    "creator": creator,
                    "pr_count": len(formatted_prs),
                    "pull_requests": formatted_prs,
                    "message": f"Found {len(formatted_prs)} open PRs by {creator}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "pull_requests": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def get_my_issues(
        self,
        token: str,
        repo: str,
        creator: str,
        state: str = "open",
        per_page: int = 10,
    ) -> dict:
        """List issues created by a specific user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "state": state,
                        "creator": creator,
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                issues = response.json()
                # Filter out PRs (they appear as issues in the API)
                issues = [i for i in issues if "pull_request" not in i]
                formatted_issues = []
                for issue in issues:
                    formatted_issues.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "created_at": issue["created_at"],
                        "updated_at": issue["updated_at"],
                        "comments": issue["comments"],
                    })
                return {
                    "success": True,
                    "creator": creator,
                    "issue_count": len(formatted_issues),
                    "issues": formatted_issues,
                    "message": f"Found {len(formatted_issues)} issues by {creator}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "issues": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type=StepType.TOOL)
    async def get_notifications(
        self,
        token: str,
        all: bool = False,
        participating: bool = False,
        per_page: int = 30,
    ) -> dict:
        """Fetch GitHub notifications."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.github.com/notifications",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "all": str(all).lower(),
                        "participating": str(participating).lower(),
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                notifications = response.json()
                formatted_notifications = []
                for notification in notifications:
                    subject = notification.get("subject", {})
                    repo = notification.get("repository", {})
                    formatted_notifications.append({
                        "id": notification["id"],
                        "reason": notification["reason"],
                        "unread": notification["unread"],
                        "updated_at": notification["updated_at"],
                        "subject_title": subject.get("title"),
                        "subject_type": subject.get("type"),
                        "subject_url": subject.get("url"),
                        "repository": repo.get("full_name"),
                    })
                return {
                    "success": True,
                    "notification_count": len(formatted_notifications),
                    "notifications": formatted_notifications,
                    "message": f"Retrieved {len(formatted_notifications)} notifications",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "notifications": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


