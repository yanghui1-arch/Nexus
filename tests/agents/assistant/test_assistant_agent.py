from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio

from src.agents.assistant.agent import Assistant


EXPECTED_TOOLS = {
    "RunCommand",
    "ReadFile",
    "ListFiles",
    "list_open_pull_requests",
    "get_pull_request",
    "get_pr_files",
    "get_pr_check_summary",
    "get_pr_reviews",
    "get_pr_review_comments",
    "get_pr_comments",
    "reply_to_pr",
    "reply_to_pr_review_comment",
    "create_pr_review",
    "merge_pr",
    "get_notifications",
    "send_discord_dm",
    "send_discord_message",
}

FORBIDDEN_TOOLS = {
    "RunCode",
    "CreateFile",
    "AppendFile",
    "EditFile",
    "pr_to_github",
    "create_github_issue",
    "create_task_work_items",
    "finish_current_task_work_item",
}


def make_assistant() -> Assistant:
    """Create an Assistant test instance."""
    return Assistant.create(
        base_url="https://api.example.com/v1",
        api_key="api-key",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_repo="owner/repo",
        github_token="github-token",
        discord_bot_token="discord-token",
        discord_user_id="discord-user",
        review_test_commands={"owner/repo": ["pytest"]},
        sandbox_workspace_key="workspace-key",
    )


def _tool_name(definition) -> str:
    return definition["function"]["name"]


def configure_empty_project_checkout(sandbox) -> None:
    """Configure a sandbox mock for checkout without installed skills."""
    sandbox.recreate = AsyncMock()
    sandbox.run_shell = AsyncMock(side_effect=[
        {"success": True, "stdout": "new", "stderr": ""},
        {"success": True, "stdout": "", "stderr": ""},
    ])
    sandbox.read_file = AsyncMock(return_value={"success": False, "content": None})
    sandbox.list_files = AsyncMock(return_value={"success": False, "files": []})


def test_assistant_tool_definitions_are_review_scoped():
    """Verify Assistant tool schema stays review scoped."""
    tool_names = {_tool_name(definition) for definition in make_assistant().tool_definitions}

    assert tool_names == EXPECTED_TOOLS
    assert FORBIDDEN_TOOLS.isdisjoint(tool_names)


def test_assistant_tool_kits_are_review_scoped():
    """Verify Assistant runtime tools stay review scoped."""

    async def run():
        sandbox = SimpleNamespace(
            run_shell=AsyncMock(),
            read_file=AsyncMock(),
            list_files=AsyncMock(),
        )
        configure_empty_project_checkout(sandbox)
        pool = SimpleNamespace(acquire=AsyncMock(return_value=sandbox), release=AsyncMock())
        assistant = make_assistant()
        assistant.set_nexus_task_context(
            SimpleNamespace(
                task_id="task-id",
                database=SimpleNamespace(),
                repo="owner/repo",
                project="nexus",
            )
        )

        with patch("src.agents.assistant.agent.get_sandbox_pool_manager", return_value=pool):
            async with assistant:
                assert set(assistant.tool_kits) == EXPECTED_TOOLS
                assert FORBIDDEN_TOOLS.isdisjoint(assistant.tool_kits)
                assert "- GitHub repo: owner/repo" in assistant.system_prompt
                assert '"owner/repo": ["pytest"]' in assistant.system_prompt
        pool.acquire.assert_awaited_once()
        pool.release.assert_awaited_once_with(sandbox)

    anyio.run(run)
