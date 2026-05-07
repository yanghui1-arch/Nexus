"""
Tests for the Sophie agent.

Sophie is a React developer and web designer with Anthropic-style design expertise.
These tests verify her capabilities and tool access.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.sophie import Sophie
from src.agents.base.agent import ModelConfig
from src.sandbox import PYTHON_312


def make_pool_manager(mock_sandbox):
    pool_manager = AsyncMock()
    pool_manager.acquire = AsyncMock(return_value=mock_sandbox)
    pool_manager.release = AsyncMock(return_value=None)
    return pool_manager


class TestSophieCreation:
    """Test Sophie agent creation and configuration."""

    def test_create_with_factory(self):
        """Test creating Sophie using the factory method."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
            github_token="test-token",
        )
        
        assert sophie.name == "Sophie"
        assert sophie.base_url == "https://api.openai.com/v1"
        assert sophie.api_key == "test-key"
        assert sophie.github_repo == "test/repo"
        assert sophie.github_token == "test-token"
        assert sophie.llm_config.model == "gpt-4"
        assert sophie.llm_config.max_length_context == 8192

    def test_create_with_custom_sandbox(self):
        """Test creating Sophie with custom sandbox config."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
            sandbox_config=PYTHON_312,
        )
        
        assert sophie.sandbox_config == PYTHON_312

    def test_create_with_max_attempts(self):
        """Test creating Sophie with custom max attempts."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
            max_attempts=50,
        )
        
        assert sophie.max_attempts == 50


class TestSophieSystemPrompt:
    """Test Sophie's system prompt content."""

    def test_system_prompt_contains_design_philosophy(self):
        """Test that system prompt includes Anthropic design principles."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        prompt = sophie.system_prompt
        
        # Check for design philosophy keywords (case-insensitive for human-centered)
        assert "Clarity" in prompt
        assert "Craft" in prompt
        assert "Trust" in prompt
        assert "Thoughtfulness" in prompt
        assert "human-centered" in prompt.lower()

    def test_system_prompt_contains_react_capabilities(self):
        """Test that system prompt includes React development capabilities."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        prompt = sophie.system_prompt
        
        # Check for React-related content
        assert "React" in prompt
        assert "TypeScript" in prompt or "component" in prompt

    def test_system_prompt_contains_workflow(self):
        """Test that system prompt includes workflow instructions."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        prompt = sophie.system_prompt
        
        # Check for workflow steps
        assert "Understand" in prompt
        assert "Research" in prompt
        assert "Design" in prompt


@pytest.mark.asyncio
class TestSophieAsyncContext:
    """Test Sophie's async context manager functionality."""

    async def test_async_context_manager_initializes_sandbox(self):
        """Test that async context manager initializes sandbox."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            async with sophie as s:
                assert s._sandbox is not None

        mock_pool_manager.acquire.assert_awaited_once()

    async def test_async_context_manager_cleans_up(self):
        """Test that async context manager properly cleans up."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            async with sophie:
                pass

        mock_pool_manager.release.assert_awaited_once_with(mock_sandbox)

    @patch("src.agents.sophie.agent.GithubTools")
    async def test_tool_kits_initialized(self, mock_github_kit_class):
        """Test that tool kits are properly initialized."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        mock_sandbox_tools = MagicMock()
        mock_sandbox_tools.all_tools = {
            "RunCode": AsyncMock(),
            "RunCommand": AsyncMock(),
            "WriteFile": AsyncMock(),
            "ReadFile": AsyncMock(),
            "AppendFile": AsyncMock(),
            "EditFile": AsyncMock(),
            "ListFiles": AsyncMock(),
        }
        mock_github_kit_class.return_value.all_tools = {
            "get_issue_comments": AsyncMock(),
            "pr_to_github": AsyncMock(),
            "get_notifications": AsyncMock(),
        }

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
                mock_toolkit_class.return_value = mock_sandbox_tools

                sophie = Sophie.create(
                    base_url="https://api.openai.com/v1",
                    api_key="test-key",
                    model="gpt-4",
                    max_context=8192,
                    github_repo="test/repo",
                )

                async with sophie as s:
                    assert s.tool_kits is not None
                    assert "get_issue_comments" in s.tool_kits
                    assert "pr_to_github" in s.tool_kits
                    assert "get_notifications" in s.tool_kits


@pytest.mark.asyncio
class TestSophieCompact:
    """Test Sophie inherits the shared compact behavior."""

    async def test_compact_single_turn_is_unchanged(self):
        with patch("src.agents.base.agent.AsyncOpenAI"):
            sophie = Sophie.create(
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                model="gpt-4",
                max_context=8192,
                github_repo="test/repo",
            )
        sophie.openai_client.chat.completions.create = AsyncMock()

        context = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Current request"},
        ]

        assert await sophie.compact(context) == context

    async def test_compact_summarizes_previous_work(self):
        with patch("src.agents.base.agent.AsyncOpenAI"):
            sophie = Sophie.create(
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                model="gpt-4",
                max_context=8192,
                github_repo="test/repo",
            )
        sophie.openai_client.chat.completions.create = AsyncMock()

        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="Earlier work"))]
        sophie.openai_client.chat.completions.create.return_value = completion
        context = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Old request"},
            {"role": "assistant", "content": "Old answer"},
            {"role": "user", "content": "Current request"},
        ]

        result = await sophie.compact(context)

        assert result == [
            {
                "role": "system",
                "content": "System\n\n## Previous Work Summary\n\nEarlier work",
            },
            {"role": "user", "content": "Current request"},
        ]


class TestSophieLastReport:
    """Test Sophie's last report functionality."""

    def test_last_report_finds_last_assistant_message(self):
        """Test that last report finds the last assistant message."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        context = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "User 2"},
            {"role": "assistant", "content": "Response 2"},
        ]
        
        result = sophie.last_report_current_process(context)
        assert result == "Response 2"

    def test_last_report_default_message(self):
        """Test default message when no assistant message found."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        context = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User 1"},
        ]
        
        result = sophie.last_report_current_process(context)
        assert "Sophie reached the maximum number of attempts" in result


class TestSophieToolAccess:
    """Test that Sophie has access to expected tools."""

    @pytest.mark.asyncio
    async def test_sophie_has_sandbox_tools(self):
        """Test that Sophie has access to sandbox tools."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
                mock_sandbox_tools = MagicMock()
                mock_sandbox_tools.all_tools = {
                    "RunCode": AsyncMock(),
                    "RunCommand": AsyncMock(),
                    "WriteFile": AsyncMock(),
                    "ReadFile": AsyncMock(),
                    "AppendFile": AsyncMock(),
                    "EditFile": AsyncMock(),
                    "ListFiles": AsyncMock(),
                }
                mock_toolkit_class.return_value = mock_sandbox_tools

                sophie = Sophie.create(
                    base_url="https://api.openai.com/v1",
                    api_key="test-key",
                    model="gpt-4",
                    max_context=8192,
                    github_repo="test/repo",
                )

                async with sophie as s:
                    assert "RunCode" in s.tool_kits
                    assert "RunCommand" in s.tool_kits
                    assert "WriteFile" in s.tool_kits
                    assert "ReadFile" in s.tool_kits
                    assert "EditFile" in s.tool_kits
                    assert "ListFiles" in s.tool_kits

    @pytest.mark.asyncio
    async def test_sophie_has_github_tools(self):
        """Test that Sophie has access to GitHub tools."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
                mock_sandbox_tools = MagicMock()
                mock_sandbox_tools.all_tools = {}
                mock_toolkit_class.return_value = mock_sandbox_tools

                sophie = Sophie.create(
                    base_url="https://api.openai.com/v1",
                    api_key="test-key",
                    model="gpt-4",
                    max_context=8192,
                    github_repo="test/repo",
                )

                async with sophie as s:
                    assert "get_issue_comments" in s.tool_kits
                    assert "reply_to_issue" in s.tool_kits
                    assert "get_pr_reviews" in s.tool_kits
                    assert "get_pr_review_comments" in s.tool_kits
                    assert "reply_to_pr_review_comment" in s.tool_kits
                    assert "get_pr_comments" in s.tool_kits
                    assert "reply_to_pr" in s.tool_kits
                    assert "get_my_open_prs" in s.tool_kits
                    assert "get_my_issues" in s.tool_kits
                    assert "get_notifications" in s.tool_kits
                    assert "pr_to_github" in s.tool_kits

    @pytest.mark.asyncio
    async def test_sophie_has_web_tools(self):
        """Test that Sophie has access to web tools."""
        mock_sandbox = AsyncMock()
        mock_pool_manager = make_pool_manager(mock_sandbox)

        with patch("src.agents.sophie.agent.get_sandbox_pool_manager", return_value=mock_pool_manager):
            with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
                mock_sandbox_tools = MagicMock()
                mock_sandbox_tools.all_tools = {}
                mock_toolkit_class.return_value = mock_sandbox_tools

                sophie = Sophie.create(
                    base_url="https://api.openai.com/v1",
                    api_key="test-key",
                    model="gpt-4",
                    max_context=8192,
                    github_repo="test/repo",
                )

                async with sophie as s:
                    assert "WebFetch" in s.tool_kits
                    assert "WebSearch" in s.tool_kits












