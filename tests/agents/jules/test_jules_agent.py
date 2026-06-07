from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base.agent import ModelConfig
from src.agents.jules import Jules
from src.sandbox import PYTHON_312, SPRING_BOOT_JAVA_21


def make_jules(**kwargs) -> Jules:
    """Create a Jules with a mocked OpenAI client."""
    with patch("src.agents.base.agent.AsyncOpenAI"):
        jules = Jules(
            name="Jules",
            tool_kits=None,
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="test",
            llm_config=ModelConfig(model="gpt-4o", max_length_context=128_000),
            max_attempts=10,
            **kwargs,
        )
    jules.openai_client.chat.completions.create = AsyncMock()
    return jules


def make_pool_manager(mock_sandbox):
    """Create a mocked sandbox pool manager."""
    pool_manager = AsyncMock()
    pool_manager.acquire = AsyncMock(return_value=mock_sandbox)
    pool_manager.release = AsyncMock(return_value=None)
    return pool_manager


def make_stop_response(content: str = "done"):
    """Build a minimal streaming response that stops."""
    async def _stream():
        """Yield mocked streaming completion chunks."""
        delta = SimpleNamespace(content=content, tool_calls=None, reasoning_content=None)
        choice = SimpleNamespace(finish_reason="stop", delta=delta)
        chunk = SimpleNamespace(choices=[choice], usage=SimpleNamespace(total_tokens=42))
        yield chunk
    return _stream()


class TestJulesCreation:
    def test_create_sets_spring_boot_defaults(self):
        """Verify create sets Spring Boot defaults."""
        with patch("src.agents.base.agent.AsyncOpenAI"):
            jules = Jules.create(
                base_url="http://x",
                api_key="k",
                model="gpt-4o",
                max_context=128_000,
                github_repo="owner/repo",
            )

        assert jules.name == "Jules"
        assert jules.llm_config.model == "gpt-4o"
        assert jules.max_attempts == 30
        assert jules.github_token is None
        assert jules.sandbox_config == SPRING_BOOT_JAVA_21

    def test_create_accepts_overrides(self):
        """Verify create accepts overrides."""
        with patch("src.agents.base.agent.AsyncOpenAI"):
            jules = Jules.create(
                base_url="http://x",
                api_key="k",
                model="gpt-4o-mini",
                max_context=128_000,
                github_repo="owner/repo",
                github_token="ghp_abc",
                sandbox_config=PYTHON_312,
            )

        assert jules.llm_config.model == "gpt-4o-mini"
        assert jules.github_token == "ghp_abc"
        assert jules.sandbox_config == PYTHON_312


@pytest.mark.asyncio
class TestJulesContextManager:
    async def test_enter_starts_sandbox_with_spring_boot_config(self):
        """Verify enter starts Spring Boot sandbox."""
        jules = make_jules()
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.jules.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            async with jules:
                assert jules._sandbox is mock_sandbox

        mock_pool_manager.acquire.assert_awaited_once_with(
            config=SPRING_BOOT_JAVA_21,
            repo_url=None,
            workspace_key=None,
        )

    async def test_tool_kits_populated_after_enter(self):
        """Verify tool kits populated after enter."""
        jules = make_jules()
        mock_sandbox = AsyncMock()

        with patch("src.agents.jules.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with jules:
                assert jules.tool_kits is not None
                assert "RunCode" in jules.tool_kits
                assert "create_github_issue" in jules.tool_kits
                assert "pr_to_github" in jules.tool_kits
                assert "bind_pr_to_task" in jules.tool_kits
                assert "WebFetch" in jules.tool_kits
                assert "web_search_agent" in jules.tool_kits

    async def test_step_raises_without_context_manager(self):
        """Verify step raises without context manager."""
        jules = make_jules()
        with pytest.raises(RuntimeError, match="async context manager"):
            await jules.step([])

    async def test_step_passes_all_tools_to_openai(self):
        """Verify all tools passed to OpenAI."""
        from src.agents.jules.agent import _ALL_TOOL_DEFINITIONS

        jules = make_jules()
        mock_sandbox = AsyncMock()

        with patch("src.agents.jules.agent.get_sandbox_pool_manager", return_value=make_pool_manager(mock_sandbox)):
            async with jules:
                jules.openai_client.chat.completions.create.return_value = make_stop_response()
                await jules.step([])
                call_kwargs = jules.openai_client.chat.completions.create.call_args

        tools_passed = call_kwargs.kwargs["tools"]
        tool_names = {tool["function"]["name"] for tool in tools_passed}
        assert tool_names == {tool["function"]["name"] for tool in _ALL_TOOL_DEFINITIONS}


class TestJulesReport:
    def test_last_report_returns_last_assistant_content(self):
        """Verify last report returns last assistant content."""
        jules = make_jules()
        ctx = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "final thought"},
        ]

        assert jules.last_report_current_process(ctx) == "final thought"

    def test_last_report_fallback_when_no_assistant(self):
        """Verify last report fallback when no assistant."""
        jules = make_jules()
        result = jules.last_report_current_process(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
        )

        assert "Jules reached the maximum number of attempts" in result
