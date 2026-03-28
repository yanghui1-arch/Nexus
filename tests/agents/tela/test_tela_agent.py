"""Unit tests for Tela.

All tests use mocked OpenAI client and a mocked Docker sandbox so they run
without any real API keys or Docker daemon.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.tela import Tela
from src.agents.base.agent import ModelConfig
from src.tools.code.github_tools import GithubToolKit
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)



def make_tela(**kwargs) -> Tela:
    """Create a Tela with a mocked OpenAI client."""
    with patch("src.agents.base.agent.OpenAI"):
        return Tela(
            name="Tela",
            tool_kits=None,
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="test",
            llm_config=ModelConfig(model="gpt-4o", max_length_context=128_000),
            max_attempts=10,
            **kwargs,
        )


def make_stop_response(content: str = "done"):
    """Build a minimal OpenAI chat completion response that stops."""
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message.content = content
    choice.message.tool_calls = None
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
    choice.message.content = None
    choice.message.tool_calls = [tc]
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.total_tokens = 20
    return resp


class TestContextManager:
    async def test_enter_starts_sandbox(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                assert tela._sandbox is mock_sandbox
                mock_sandbox.__aenter__.assert_awaited_once()


    async def test_exit_stops_sandbox(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                pass

        mock_sandbox.__aexit__.assert_awaited_once()
        assert tela._sandbox is None


    async def test_tool_kits_populated_after_enter(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                assert tela.tool_kits is not None
                assert "RunCode" in tela.tool_kits
                assert "FetchFromGithub" in tela.tool_kits
                assert "PrToGithub" in tela.tool_kits
                assert "WebFetch" in tela.tool_kits
                assert "WebSearch" in tela.tool_kits


    async def test_step_raises_without_context_manager(self):
        tela = make_tela()
        with pytest.raises(RuntimeError, match="async context manager"):
            tela.step([])

    async def test_enter_forks_when_not_exists(self):
        tela = make_tela(github_repo="owner/repo", github_token="ghp_test")
        mock_sandbox = AsyncMock()

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            with patch("src.agents.tela.agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(status_code=404)
                mock_http.post.return_value = MagicMock(status_code=202)
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

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            with patch("src.agents.tela.agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(status_code=200)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                async with tela:
                    pass

        mock_http.post.assert_not_awaited()

    async def test_enter_injects_fork_urls_into_system_prompt(self):
        tela = make_tela(github_repo="owner/repo", github_token="ghp_test")
        mock_sandbox = AsyncMock()

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            with patch("src.agents.tela.agent.httpx.AsyncClient") as mock_client_cls:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(status_code=200)
                mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                async with tela:
                    assert "Nexus-Tela/repo" in tela.system_prompt
                    assert "owner/repo" in tela.system_prompt
                    assert "upstream" in tela.system_prompt


class TestStep:
    async def test_stop_result_parsed_correctly(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_stop_response("all done")
                result = tela.step([{"role": "user", "content": "hello"}])

        assert result.finish_reason == "stop"
        assert result.completion_content == "all done"
        assert result.tool_calls is None


    async def test_tool_call_result_parsed_correctly(self):
        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_tool_response(
                    "RunCode", '{"code": "print(1)"}'
                )
                result = tela.step([{"role": "user", "content": "run code"}])

        assert result.finish_reason == "tool_calls"
        assert result.tool_calls is not None
        assert result.tool_calls[0].function.name == "RunCode"


    async def test_all_tools_passed_to_openai(self):
        from src.agents.tela.agent import _ALL_TOOL_DEFINITIONS

        tela = make_tela()
        mock_sandbox = AsyncMock()
        mock_sandbox._workdir = "/tmp/nexus_test"

        with patch("src.agents.tela.agent.Sandbox", return_value=mock_sandbox):
            async with tela:
                tela.openai_client.chat.completions.create.return_value = make_stop_response()
                tela.step([])

        call_kwargs = tela.openai_client.chat.completions.create.call_args
        tools_passed = call_kwargs.kwargs["tools"]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert tool_names == {t["function"]["name"] for t in _ALL_TOOL_DEFINITIONS}


class TestGithubToolKit:
    """GithubToolKit runs git operations inside the sandbox container."""

    def _make_kit(self) -> GithubToolKit:
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        return GithubToolKit(sandbox)

    async def test_fetch_clones_when_no_git_dir(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},   # test -d .git
            {"success": True, "stdout": "", "stderr": ""},       # git clone
        ])
        kit = GithubToolKit(sandbox)
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
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "exists", "stderr": ""},  # test -d .git
            {"success": True, "stdout": "", "stderr": ""},         # git fetch/checkout/pull
        ])
        kit = GithubToolKit(sandbox)
        result = await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
        )
        assert result["success"] is True
        pull_call = sandbox.run_shell.call_args_list[1][0][0]
        assert "pull" in pull_call

    async def test_fetch_sets_upstream_remote_after_clone(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},   # test -d .git
            {"success": True, "stdout": "", "stderr": ""},       # git clone
            {"success": True, "stdout": "", "stderr": ""},       # git remote add upstream
        ])
        kit = GithubToolKit(sandbox)
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
        kit = GithubToolKit(sandbox)
        await kit.fetch_from_github(
            repo_url="https://github.com/Nexus-Tela/repo",
            local_path="/workspace/myproject",
        )
        assert sandbox.run_shell.call_count == 2

    async def test_fetch_injects_token_into_url(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(side_effect=[
            {"success": True, "stdout": "new", "stderr": ""},
            {"success": True, "stdout": "", "stderr": ""},
        ])
        kit = GithubToolKit(sandbox)
        await kit.fetch_from_github(
            repo_url="https://github.com/owner/repo",
            local_path="/workspace/myproject",
            token="ghp_secret",
        )
        clone_call = sandbox.run_shell.call_args_list[1][0][0]
        assert "x-access-token:ghp_secret@github.com" in clone_call

    async def test_pr_pushes_via_sandbox(self):
        sandbox = AsyncMock()
        sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        kit = GithubToolKit(sandbox)
        with patch("src.tools.code.github_tools.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"html_url": "https://github.com/owner/repo/pull/1", "number": 1}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=mock_resp)))
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await kit.pr_to_github(
                token="tok",
                repo="owner/repo",
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
        kit = GithubToolKit(sandbox)
        captured_body: list[str] = []
        with patch("src.tools.code.github_tools.httpx.AsyncClient") as mock_client_cls:
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


class TestCompact:
    def test_short_context_unchanged(self):
        tela = make_tela()
        ctx = [{"role": "system", "content": "s"}] * 5
        assert tela.compact(ctx) == ctx

    def test_long_context_keeps_system_and_recent(self):
        tela = make_tela()
        system = {"role": "system", "content": "sys"}
        first_user = {"role": "user", "content": "first"}
        middle = [{"role": "assistant", "content": f"msg{i}"} for i in range(20)]
        recent = [{"role": "assistant", "content": f"recent{i}"} for i in range(10)]
        ctx = [system, first_user] + middle + recent

        result = tela.compact(ctx)

        assert result[0] == system
        assert first_user in result
        for msg in recent:
            assert msg in result
        # middle messages should be dropped
        for msg in middle:
            assert msg not in result


class TestFactory:
    def test_create_sets_correct_defaults(self):
        with patch("src.agents.base.agent.OpenAI"):
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
        with patch("src.agents.base.agent.OpenAI"):
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
