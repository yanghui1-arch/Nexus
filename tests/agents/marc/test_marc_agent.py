from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio

from src.agents.marc.agent import Marc, _ALL_TOOL_DEFINITIONS


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
    "reply_to_issue",
    "reply_to_pr",
    "reply_to_pr_review_comment",
    "create_task_work_items",
    "finish_current_task_work_item",
}


def make_marc() -> Marc:
    return Marc.create(
        base_url="https://api.example.com/v1",
        api_key="api-key",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_repo="owner/repo",
        github_token="github-token",
    )


def _tool_name(definition) -> str:
    if isinstance(definition, dict):
        return definition["function"]["name"]
    return definition["function"]["name"]


def test_marc_tool_kits_are_read_only():
    async def run():
        sandbox = SimpleNamespace(
            run_code=AsyncMock(),
            run_shell=AsyncMock(),
            read_file=AsyncMock(),
            list_files=AsyncMock(),
        )
        pool = SimpleNamespace(acquire=AsyncMock(return_value=sandbox), release=AsyncMock())
        marc = make_marc()
        marc.set_nexus_task_context(SimpleNamespace(task_id="task-id", database=SimpleNamespace(), repo="owner/repo"))
        with patch("src.agents.marc.agent.get_sandbox_pool_manager", return_value=pool):
            async with marc:
                assert set(marc.tool_kits) == EXPECTED_TOOLS
                assert FORBIDDEN_MUTATING_TOOLS.isdisjoint(marc.tool_kits)
        pool.acquire.assert_awaited_once()
        pool.release.assert_awaited_once_with(sandbox)

    anyio.run(run)


def test_marc_tool_definitions_include_only_expected_read_only_tools():
    tool_names = {_tool_name(definition) for definition in _ALL_TOOL_DEFINITIONS}

    assert tool_names == EXPECTED_TOOLS
    assert FORBIDDEN_MUTATING_TOOLS.isdisjoint(tool_names)



def test_marc_step_passes_read_only_tools_to_openai():
    async def run():
        marc = make_marc()
        marc._sandbox = SimpleNamespace()

        async def fake_stream():
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
