from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio

from src.agents.marc.agent import Marc


EXPECTED_TOOLS = {
    "RunCommand",
    "web_search_agent",
    "ListGithubIssues",
    "GetGithubIssue",
    "ListGithubPullRequests",
    "GetGithubPullRequest",
    "create_proposal",
    "create_feature_for_product_proposal",
    "create_feature_item",
}

FORBIDDEN_MUTATING_TOOLS = {
    "RunCode",
    "ReadFile",
    "ListFiles",
    "CreateFile",
    "AppendFile",
    "EditFile",
    "pr_to_github",
    "bind_pr_to_task",
    "reply_to_issue",
    "reply_to_pr",
    "reply_to_pr_review_comment",
    "send_discord_dm",
    "send_discord_channel_message",
    "reply_to_discord_channel_message",
    "create_task_work_items",
    "finish_current_task_work_item",
}


def make_marc() -> Marc:
    """Create a Marc test instance."""
    return Marc.create(
        base_url="https://api.example.com/v1",
        api_key="api-key",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_repo="owner/repo",
        github_token="github-token",
    )


def configure_empty_project_checkout(sandbox) -> None:
    """Configure a sandbox mock for a successful checkout without skills."""
    sandbox.recreate = AsyncMock()
    sandbox.run_shell = AsyncMock(side_effect=[
        {"success": True, "stdout": "new", "stderr": ""},
        {"success": True, "stdout": "", "stderr": ""},
    ])
    sandbox.read_file = AsyncMock(return_value={"success": False, "content": None})
    sandbox.list_files = AsyncMock(return_value={"success": False, "files": []})


def _tool_name(definition) -> str:
    """Return a tool definition name."""
    if isinstance(definition, dict):
        return definition["function"]["name"]
    return definition["function"]["name"]


def test_marc_tool_kits_are_read_only():
    """Verify marc tool kits are read only."""
    async def run():
        """Run the async test body."""
        sandbox = SimpleNamespace(
            run_code=AsyncMock(),
            run_shell=AsyncMock(),
            read_file=AsyncMock(),
            list_files=AsyncMock(),
        )
        configure_empty_project_checkout(sandbox)
        pool = SimpleNamespace(acquire=AsyncMock(return_value=sandbox), release=AsyncMock())
        marc = make_marc()
        marc.set_nexus_task_context(
            SimpleNamespace(
                task_id="task-id",
                database=SimpleNamespace(),
                repo="owner/repo",
                project="nexus",
            )
        )
        with patch("src.agents.marc.agent.get_sandbox_pool_manager", return_value=pool):
            async with marc:
                assert set(marc.tool_kits) == EXPECTED_TOOLS
                assert FORBIDDEN_MUTATING_TOOLS.isdisjoint(marc.tool_kits)
                assert "- Project: nexus" in marc.system_prompt
        pool.acquire.assert_awaited_once()
        pool.release.assert_awaited_once_with(sandbox)

    anyio.run(run)


def test_marc_tool_definitions_include_only_expected_read_only_tools():
    """Verify marc tool definitions include only expected read only tools."""
    tool_names = {_tool_name(definition) for definition in make_marc().tool_definitions}

    assert tool_names == EXPECTED_TOOLS
    assert FORBIDDEN_MUTATING_TOOLS.isdisjoint(tool_names)



def test_marc_step_passes_read_only_tools_to_openai():
    """Verify marc step passes read only tools to openai."""
    async def run():
        """Run the async test body."""
        marc = make_marc()
        marc._sandbox = SimpleNamespace()

        async def fake_stream():
            """Return a fake stream completion result."""
            yield SimpleNamespace(
                choices=[SimpleNamespace(
                    finish_reason="stop",
                    delta=SimpleNamespace(content="done", tool_calls=None),
                )],
                usage=SimpleNamespace(total_tokens=12),
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=fake_stream()))
            )
        )
        marc.openai_client = fake_client

        await marc.step([{"role": "user", "content": "research"}])

        kwargs = fake_client.chat.completions.create.await_args.kwargs
        assert {_tool_name(definition) for definition in kwargs["tools"]} == EXPECTED_TOOLS

    anyio.run(run)
