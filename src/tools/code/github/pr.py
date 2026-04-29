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

PR_TO_GITHUB = pydantic_function_tool(PrToGithub, name="pr_to_github")
GET_PR_REVIEWS = pydantic_function_tool(GetPRReviews, name="get_pr_reviews")
GET_PR_REVIEW_COMMENTS = pydantic_function_tool(GetPRReviewComments, name="get_pr_review_comments")
REPLY_TO_PR_REVIEW_COMMENT = pydantic_function_tool(ReplyToPRReviewComment, name="reply_to_pr_review_comment")
GET_PR_COMMENTS = pydantic_function_tool(GetPRComments, name="get_pr_comments")
REPLY_TO_PR = pydantic_function_tool(ReplyToPR, name="reply_to_pr")
GET_MY_OPEN_PRS = pydantic_function_tool(GetMyOpenPRs, name="get_my_open_prs")
