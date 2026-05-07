"""Unit tests for Tela.

All tests use mocked OpenAI client and a mocked Docker sandbox so they run
without any real API keys or Docker daemon.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.tela import Tela
from src.agents.base.agent import ModelConfig
from src.tools.code.github.client import GithubTools
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)



def make_tela(**kwargs) -> Tela:
    """Create a Tela with a mocked OpenAI client."""
    with patch("src.agents.base.agent.AsyncOpenAI"):
        tela = Tela(
            name="Tela",
            tool_kits=None,
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="test",
            llm_config=ModelConfig(model="gpt-4o", max_length_context=128_000),
            max_attempts=10,
            **kwargs,
        )
    tela.openai_client.chat.completions.create = AsyncMock()
    return tela


def make_pool_manager(mock_sandbox):
    pool_manager = AsyncMock()
    pool_manager.acquire = AsyncMock(return_value=mock_sandbox)
    pool_manager.release = AsyncMock(return_value=None)
    return pool_manager


def make_stop_response(content: str = "done"):
    """Build a minimal OpenAI chat completion response that stops."""
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = ChatCompletionMessage(role="assistant", content=content)
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.total_tokens = 42
    return resp


def make_tool_response(name: str, args: str, call_id: str = "c1"):
    """Build a response that requests one tool call."""
    tc = ChatCompletionMessageToolCall(
        id=call_id, type="function", function=Function(name=name, arguments=args)
    )
    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[tc])
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.total_tokens = 20
    return resp


class TestContextManager:
    async def test_enter_starts_sandbox(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            async with tela:
                assert tela._sandbox is mock_sandbox

        mock_pool_manager.acquire.assert_awaited_once()


    async def test_exit_stops_sandbox(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            async with tela:
                pass

        mock_pool_manager.release.assert_awaited_once_with(mock_sandbox)
        assert tela._sandbox is None


    async def test_tool_kits_populated_after_enter(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with tela:
                assert tela.tool_kits is not None
                assert "RunCode" in tela.tool_kits
                assert "get_issue_comments" in tela.tool_kits
                assert "pr_to_github" in tela.tool_kits
                assert "WebFetch" in tela.tool_kits
                assert "WebSearch" in tela.tool_kits


    async def test_step_raises_without_context_manager(self):
        tela = make_tela()
        with pytest.raises(RuntimeError, match="async context manager"):
            await tela.step([])

    async def test_enter_forks_when_not_exists(self):
        tela = make_tela(github_repo="owner/repo", github_token="ghp_test")
        mock_sandbox = AsyncMock()

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get = AsyncMock(side_effect=[
                    MagicMock(status_code=404),
                    MagicMock(
                        status_code=200,
                        json=MagicMock(return_value={"fork": True, "parent": {"full_name": "owner/repo"}}),
                    ),
                ])
                mock_http.post.return_value = MagicMock(status_code=202, text="accepted")
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                async with tela:
                    pass

        mock_http.post.assert_awaited_once()
        post_url = mock_http.post.call_args[0][0]
        assert "owner/repo/forks" in post_url

    async def test_enter_skips_fork_creation_when_exists(self):
        tela = make_tela(github_repo="owner/repo", github_token="ghp_test")
        mock_sandbox = AsyncMock()

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"fork": True, "parent": {"full_name": "owner/repo"}}),
                )
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                async with tela:
                    pass

        mock_http.post.assert_not_awaited()

    async def test_enter_injects_fork_urls_into_system_prompt(self):
        tela = make_tela(github_repo="owner/repo", github_token="ghp_test")
        mock_sandbox = AsyncMock()

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"fork": True, "parent": {"full_name": "owner/repo"}}),
                )
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                async with tela:
                    assert "Nexus-Tela/repo" in tela.system_prompt
                    assert "owner/repo" in tela.system_prompt
                    assert "Upstream repo" in tela.system_prompt
                    assert "Upstream URL" in tela.system_prompt


class TestStep:
    async def test_stop_result_parsed_correctly(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_stop_response("all done")
                result = await tela.step([{"role": "user", "content": "hello"}])

        assert result.finish_reason == "stop"
        assert result.completion_content == "all done"
        assert result.tool_calls is None


    async def test_tool_call_result_parsed_correctly(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_tool_response(
                    "RunCode", '{"code": "print(1)"}'
                )
                result = await tela.step([{"role": "user", "content": "run code"}])

        assert result.finish_reason == "tool_calls"
        assert result.tool_calls is not None
        assert result.tool_calls[0].function.name == "RunCode"


    async def test_all_tools_passed_to_openai(self):
        from src.agents.tela.agent import _ALL_TOOL_DEFINITIONS

        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_stop_response()
                await tela.step([])
                call_kwargs = tela.openai_client.chat.completions.create.call_args
        tools_passed = call_kwargs.kwargs["tools"]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert tool_names == {t["function"]["name"] for t in _ALL_TOOL_DEFINITIONS}


class TestGithubTools:
    """GithubTools runs git operations inside the sandbox container."""

    def _make_kit(self) -> GithubTools:
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        return GithubTools(sandbox)

    async def test_fetch_clones_when_no_git_dir(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},   # test -d .git
            {"success": True, "stdout": "", "stderr": ""},       # git clone
        ])
        kit = GithubTools(sandbox)
        result = await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
        )
        assert result["success"] is True
        clone_call = sandbox.run_shell.call_args_list[1][0][0]
        assert "git clone" in clone_call
        assert "/workspace/myproject" in clone_call

    async def test_fetch_pulls_when_already_cloned(self):
        sandbox = AsyncMock()
        sandbox.recreate = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "exists", "stderr": ""},                         # test -d .git
            {"success": True, "stdout": "https://github.com/owner/repo\n", "stderr": ""},  # origin remote
            {"success": True, "stdout": "", "stderr": ""},                                # git fetch/checkout/pull
        ])
        kit = GithubTools(sandbox)
        result = await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
        )
        assert result["success"] is True
        pull_call = sandbox.run_shell.call_args_list[2][0][0]
        assert "pull" in pull_call
        sandbox.recreate.assert_not_awaited()

    async def test_fetch_sets_upstream_remote_after_clone(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},   # test -d .git
            {"success": True, "stdout": "", "stderr": ""},       # git clone
            {"success": True, "stdout": "", "stderr": ""},       # git remote add upstream
        ])
        kit = GithubTools(sandbox)
        await kit.fetch_from_github(
            repo_url="https://github.com/Nexus-Tela/repo",
            local_path="/workspace/myproject",
            upstream_url="https://github.com/owner/repo",
        )
        upstream_cmd = sandbox.run_shell.call_args_list[2][0][0]
        assert "remote" in upstream_cmd and "upstream" in upstream_cmd
        assert "https://github.com/owner/repo" in upstream_cmd

    async def test_fetch_skips_upstream_when_not_provided(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},
            {"success": True, "stdout": "", "stderr": ""},
        ])
        kit = GithubTools(sandbox)
        await kit.fetch_from_github(
            repo_url="https://github.com/Nexus-Tela/repo",
            local_path="/workspace/myproject",
        )
        assert sandbox.run_shell.call_count == 2

    async def test_fetch_uses_repo_url_as_given(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},
            {"success": True, "stdout": "", "stderr": ""},
        ])
        kit = GithubTools(sandbox)
        authenticated_url = "https://x-access-token:ghp_secret@github.com/owner/repo"
        await kit.fetch_from_github(
            repo_url=authenticated_url,
            local_path="/workspace/myproject",
        )
        clone_call = sandbox.run_shell.call_args_list[1][0][0]
        assert authenticated_url in clone_call

    async def test_fetch_recreates_sandbox_when_origin_remote_missing(self):
        sandbox = AsyncMock()
        sandbox.recreate = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "exists", "stderr": ""},  # test -d .git
            {"success": False, "stdout": "", "stderr": "missing"}, # git remote get-url
            {"success": True, "stdout": "", "stderr": ""},         # git clone
        ])
        kit = GithubTools(sandbox)
        result = await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
        )

        assert result["success"] is True
        sandbox.recreate.assert_awaited_once()
        clone_call = sandbox.run_shell.call_args_list[2][0][0]
        assert "git clone" in clone_call

    async def test_fetch_recreates_sandbox_when_origin_remote_mismatched(self):
        sandbox = AsyncMock()
        sandbox.recreate = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "exists", "stderr": ""},                           # test -d .git
            {"success": True, "stdout": "https://github.com/other/repo\n", "stderr": ""},  # git remote get-url
            {"success": True, "stdout": "", "stderr": ""},                                  # git clone
        ])
        kit = GithubTools(sandbox)
        result = await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
        )

        assert result["success"] is True
        sandbox.recreate.assert_awaited_once()
        clone_call = sandbox.run_shell.call_args_list[2][0][0]
        assert "git clone" in clone_call

    async def test_pr_pushes_via_sandbox(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        kit = GithubTools(sandbox)
        with patch("src.tools.code.github.client.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"html_url": "https://github.com/owner/repo/pull/1", "number": 1}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=mock_resp)))
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await kit.pr_to_github(
                token="tok",
                repo="owner/repo",
                branch="feature",
                title="feat: x",
                body="body",
                head="feature",
                local_path="/workspace/myproject",
            )
        push_cmd = sandbox.run_shell.call_args[0][0]
        assert "git" in push_cmd and "push" in push_cmd and "feature" in push_cmd

    async def test_pr_appends_closes_issues(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        kit = GithubTools(sandbox)
        captured_body: list[str] = []
        with patch("src.tools.code.github.client.httpx.AsyncClient") as mock_client_cls:
            async def fake_post(*args, **kwargs):
                captured_body.append(kwargs["json"]["body"])
                resp = MagicMock()
                resp.json.return_value = {"html_url": "url", "number": 2}
                resp.raise_for_status = MagicMock()
                return resp
            mock_http = AsyncMock()
            mock_http.post = fake_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await kit.pr_to_github(
                token="tok",
                repo="owner/repo",
                branch="feature",
                title="feat",
                body="initial body",
                head="feature",
                closes_issues=[42, 7],
            )
        assert "Closes #42" in captured_body[0]
        assert "Closes #7" in captured_body[0]


class TestSopAndReport:
    def test_sop_not_implemented(self):
        tela = make_tela()
        history = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "RunCode", "arguments": '{"code":"x"}'}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "42"},
            {"role": "assistant", "content": "The answer is 42."},
        ]
        with pytest.raises(NotImplementedError):
            tela.SOP(history)


    def test_last_report_returns_last_assistant_content(self):
        tela = make_tela()
        ctx = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "first thought"},
            {"role": "assistant", "content": "final thought"},
        ]
        assert tela.last_report_current_process(ctx) == "final thought"


    def test_last_report_fallback_when_no_assistant(self):
        tela = make_tela()
        ctx = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
        result = tela.last_report_current_process(ctx)
        assert "maximum" in result.lower()


@pytest.mark.asyncio
class TestCompact:
    async def test_single_turn_is_unchanged(self):
        tela = make_tela()
        ctx = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "current task"},
        ]

        assert await tela.compact(ctx) == ctx

    async def test_compact_uses_shared_base_behavior(self):
        tela = make_tela()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="Earlier work"))]
        tela.openai_client.chat.completions.create.return_value = completion
        ctx = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "old task"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "current task"},
        ]

        result = await tela.compact(ctx)

        assert result == [
            {
                "role": "system",
                "content": "sys\n\n## Previous Work Summary\n\nEarlier work",
            },
            {"role": "user", "content": "current task"},
        ]


class TestFactory:
    def test_create_sets_correct_defaults(self):
        with patch("src.agents.base.agent.AsyncOpenAI"):
            tela = Tela.create(
                base_url="http://x",
                api_key="k",
                model="gpt-4o",
                max_context=128_000,
                github_repo="owner/repo",
            )

        assert tela.name == "Tela"
        assert tela.llm_config.model == "gpt-4o"
        assert tela.max_attempts == 30
        assert tela.github_token is None


    def test_create_accepts_overrides(self):
        with patch("src.agents.base.agent.AsyncOpenAI"):
            tela = Tela.create(
                base_url="http://x",
                api_key="k",
                model="gpt-4o-mini",
                max_context=128_000,
                github_repo="owner/repo",
                github_token="ghp_abc",
            )
        assert tela.llm_config.model == "gpt-4o-mini"
        assert tela.github_token == "ghp_abc"










