from __future__ import annotations

from openai import pydantic_function_tool
from pydantic import BaseModel, Field


class BindPrToTask(BaseModel):
    """Attach a real GitHub pull request to the current Nexus task.

    You must call this tool whenever either of these situations happens:
    1. You just created the PR for this task, such as calls `pr_to_github` or via shell, `gh pr create`, or direct
       real GitHub API calls.
    2. You are continuing work on a PR that already exists for this task, and
       will keep using that same PR for the current task.

    Examples:
    - You post a pr to github and get `https://github.com/owner/repo/pull/123`.
      Call `bind_pr_to_task` with that URL so Nexus tracks that PR.
    - You resume work on an existing PR
      `https://github.com/owner/repo/pull/123`, push more commits to it, and
      then call `bind_pr_to_task` so Nexus knows this task belongs to that same
      PR.
    """

    token: str = Field(description="GitHub personal access token with repo scope")
    pull_request_url: str = Field(
        description="GitHub pull request URL to bind to the current Nexus task. This can be a newly created PR URL or an already existing PR URL for the same task."
    )


BIND_PR_TO_TASK = pydantic_function_tool(
    BindPrToTask,
    name="bind_pr_to_task",
)

NEXUS_TASK_TOOL_DEFINITIONS: list = [
    BIND_PR_TO_TASK,
]
