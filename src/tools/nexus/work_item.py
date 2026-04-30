from __future__ import annotations

from openai import pydantic_function_tool
from pydantic import BaseModel, Field


class TaskWorkItemInput(BaseModel):
    title: str = Field(description="Short review-sized work item title")
    description: str = Field(description="Concrete implementation scope for this work item")


class CreateTaskWorkItems(BaseModel):
    """Create Nexus-owned internal work items for a large task."""

    items: list[TaskWorkItemInput] = Field(
        min_length=1,
        description="Ordered internal work items split from the original task",
    )


class FinishCurrentTaskWorkItem(BaseModel):
    """Finish the current work item and create its virtual PR. Call it after you have finished one task work item."""

    summary: str = Field(description="Reviewer-facing summary of the implemented work item")
    local_path: str | None = Field(
        default=None,
        description="Local repository path.",
    )


CREATE_TASK_WORK_ITEMS = pydantic_function_tool(
    CreateTaskWorkItems,
    name="create_task_work_items",
)
FINISH_CURRENT_TASK_WORK_ITEM = pydantic_function_tool(
    FinishCurrentTaskWorkItem,
    name="finish_current_task_work_item",
)

NEXUS_WORK_ITEM_TOOL_DEFINITIONS: list = [
    CREATE_TASK_WORK_ITEMS,
    FINISH_CURRENT_TASK_WORK_ITEM,
]
