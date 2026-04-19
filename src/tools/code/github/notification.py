from pydantic import BaseModel, Field
from openai import pydantic_function_tool

class GetNotifications(BaseModel):
    """Fetch GitHub notifications for repositories you participate in.
    Useful for discovering new activity on your PRs, issues, and mentions."""

    token: str = Field(description="GitHub personal access token with repo scope")
    all: bool = Field(default=False, description="If true, show all notifications including read ones (default: false - only unread)")
    participating: bool = Field(default=False, description="If true, only show notifications where you are directly participating (default: false)")
    per_page: int = Field(default=30, description="Number of notifications to fetch (default: 30)")

GET_NOTIFICATIONS = pydantic_function_tool(GetNotifications, name="get_notifications")
