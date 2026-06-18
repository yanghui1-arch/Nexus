from pydantic import BaseModel, Field
from openai import pydantic_function_tool

class PrToGithub(BaseModel):
    """Push the current local branch to GitHub and open a pull request.
    Requires a GitHub personal access token with repo scope."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    branch: str = Field(description="Branch that to push.")
    title: str = Field(description="Pull request title")
    body: str = Field(description="Pull request description (markdown supported)")
    head: str = Field(description="Branch that contains the changes to be merged. For cross-repo PRs from your fork, use the format `your-github-nickname:<branch>` (e.g. `Nexus-Tela:feature/my-feature`)")
    base: str = Field(default="main", description="Target branch for the PR (default: main)")
    closes_issues: list[int] = Field(
        default_factory=list,
        description="Optional GitHub issue numbers this PR resolves.",
    )
    local_path: str | None = Field(default=None, description="Local repository path to push from. Uses current working directory when omitted.")
    draft: bool = Field(default=False, description="Open as a draft pull request (default: false)")


class GetPRReviews(BaseModel):
    """Fetch all reviews on a specific pull request. Reviews include
    approval status (APPROVED, CHANGES_REQUESTED, COMMENTED) and review body."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch reviews for")


class GetPullRequest(BaseModel):
    """Fetch metadata for a pull request, including head/base refs, draft
    state, mergeability, and latest head SHA."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch")


class ListOpenPullRequests(BaseModel):
    """List open pull requests in a repository."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    per_page: int = Field(default=30, description="Number of PRs to fetch (default: 30)")


class GetPRFiles(BaseModel):
    """Fetch changed files and patches for a pull request."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to fetch files for")
    per_page: int = Field(default=100, description="Number of files to fetch (default: 100)")


class GetPRCheckSummary(BaseModel):
    """Fetch a summary of check runs and commit statuses for a pull request head."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    ref: str = Field(description="Head SHA or branch ref to inspect")


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


class CreatePRReviewComment(BaseModel):
    """Inline comment to include when creating a formal pull request review."""

    path: str = Field(description="File path to comment on")
    body: str = Field(description="Inline comment body")
    line: int | None = Field(default=None, description="Diff line to comment on")
    side: str = Field(default="RIGHT", description="Diff side, usually RIGHT")
    start_line: int | None = Field(default=None, description="Optional start line for multi-line comments")
    start_side: str | None = Field(default=None, description="Optional start side for multi-line comments")


class CreatePRReview(BaseModel):
    """Submit a formal GitHub pull request review."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to review")
    event: str = Field(description="Review event: APPROVE, REQUEST_CHANGES, or COMMENT")
    body: str = Field(description="Review body in markdown format")
    commit_id: str | None = Field(default=None, description="Optional head commit SHA the review applies to")
    comments: list[CreatePRReviewComment] = Field(
        default_factory=list,
        description="Optional inline comments for the review",
    )


class MergePR(BaseModel):
    """Merge a pull request using an expected head SHA."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    pull_number: int = Field(description="Pull request number to merge")
    sha: str = Field(description="Expected pull request head SHA. GitHub rejects merge if it changed.")
    merge_method: str = Field(default="squash", description="Merge method: merge, squash, or rebase")
    commit_title: str | None = Field(default=None, description="Optional merge commit title")
    commit_message: str | None = Field(default=None, description="Optional merge commit message")


class GetMyOpenPRs(BaseModel):
    """List open pull requests created by you in a repository.
    Useful for checking status of your PRs and finding new comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    creator: str = Field(description="GitHub username to filter PRs by (your username)")
    per_page: int = Field(default=10, description="Number of PRs to fetch (default: 10)")

PR_TO_GITHUB = pydantic_function_tool(PrToGithub, name="pr_to_github")
GET_PULL_REQUEST = pydantic_function_tool(GetPullRequest, name="get_pull_request")
LIST_OPEN_PULL_REQUESTS = pydantic_function_tool(ListOpenPullRequests, name="list_open_pull_requests")
GET_PR_FILES = pydantic_function_tool(GetPRFiles, name="get_pr_files")
GET_PR_CHECK_SUMMARY = pydantic_function_tool(GetPRCheckSummary, name="get_pr_check_summary")
GET_PR_REVIEWS = pydantic_function_tool(GetPRReviews, name="get_pr_reviews")
GET_PR_REVIEW_COMMENTS = pydantic_function_tool(GetPRReviewComments, name="get_pr_review_comments")
REPLY_TO_PR_REVIEW_COMMENT = pydantic_function_tool(ReplyToPRReviewComment, name="reply_to_pr_review_comment")
GET_PR_COMMENTS = pydantic_function_tool(GetPRComments, name="get_pr_comments")
REPLY_TO_PR = pydantic_function_tool(ReplyToPR, name="reply_to_pr")
CREATE_PR_REVIEW = pydantic_function_tool(CreatePRReview, name="create_pr_review")
MERGE_PR = pydantic_function_tool(MergePR, name="merge_pr")
GET_MY_OPEN_PRS = pydantic_function_tool(GetMyOpenPRs, name="get_my_open_prs")
