from __future__ import annotations

from openai import pydantic_function_tool
from pydantic import BaseModel, Field


class RecordAssistantEvent(BaseModel):
    """Record a short memory event for the current Assistant agent instance."""

    summary: str = Field(description="Short natural-language summary of what you did or decided.")
    task_id: str | None = Field(default=None, description="Related Nexus task id, if any.")
    pull_request_url: str | None = Field(default=None, description="Related GitHub pull request URL, if any.")
    issue_url: str | None = Field(default=None, description="Related GitHub issue URL, if any.")


class ListRecentAssistantEvents(BaseModel):
    """List recent memory events for the current Assistant agent instance."""

    limit: int = Field(default=20, description="Maximum number of events to return.")
    task_id: str | None = Field(default=None, description="Filter by Nexus task id.")
    pull_request_url: str | None = Field(default=None, description="Filter by GitHub pull request URL.")
    issue_url: str | None = Field(default=None, description="Filter by GitHub issue URL.")
    start_time: str | None = Field(
        default=None,
        description="Inclusive ISO 8601 timestamp filter, precise to seconds, for event created_at.",
    )
    end_time: str | None = Field(
        default=None,
        description="Exclusive ISO 8601 timestamp filter, precise to seconds, for event created_at.",
    )


RECORD_ASSISTANT_EVENT = pydantic_function_tool(
    RecordAssistantEvent,
    name="record_assistant_event",
)

LIST_RECENT_ASSISTANT_EVENTS = pydantic_function_tool(
    ListRecentAssistantEvents,
    name="list_recent_assistant_events",
)

NEXUS_ASSISTANT_EVENT_TOOL_DEFINITIONS: list = [
    RECORD_ASSISTANT_EVENT,
    LIST_RECENT_ASSISTANT_EVENTS,
]
