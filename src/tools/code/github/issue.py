from pydantic import BaseModel, Field
from openai import pydantic_function_tool

__all__ = [
    "GET_ISSUE_COMMENTS",
    "REPLY_TO_ISSUE",
    "GET_MY_ISSUES",
]

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

class GetMyIssues(BaseModel):
    """List issues created by you in a repository.
    Useful for tracking issues you've opened and checking for new comments."""

    token: str = Field(description="GitHub personal access token with repo scope")
    repo: str = Field(description="Repository in owner/repo format (e.g. acme/my-project)")
    creator: str = Field(description="GitHub username to filter issues by (your username)")
    state: str = Field(default="open", description="Issue state: open, closed, or all (default: open)")
    per_page: int = Field(default=10, description="Number of issues to fetch (default: 10)")

GET_ISSUE_COMMENTS = pydantic_function_tool(GetIssueComments, name="get_issue_comments")
REPLY_TO_ISSUE = pydantic_function_tool(ReplyToIssue, name="reply_to_issue")
GET_MY_ISSUES = pydantic_function_tool(GetMyIssues, name="get_my_issues")
