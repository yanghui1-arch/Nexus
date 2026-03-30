"""
Tests for the Sophie agent.

Sophie is a React developer and web designer with Anthropic-style design expertise.
These tests verify her capabilities and tool access.
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch

from src.agents.sophie import Sophie
from src.agents.base.agent import ModelConfig, SampleConfig
from src.sandbox import PYTHON_312


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

    @patch("src.agents.sophie.agent.Sandbox")
    async def test_async_context_manager_initializes_sandbox(self, mock_sandbox_class):
        """Test that async context manager initializes sandbox."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        async with sophie as s:
            assert s._sandbox is not None
            mock_sandbox.__aenter__.assert_called_once()

    @patch("src.agents.sophie.agent.Sandbox")
    async def test_async_context_manager_cleans_up(self, mock_sandbox_class):
        """Test that async context manager properly cleans up."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        async with sophie as s:
            pass
        
        mock_sandbox.__aexit__.assert_called_once()

    @patch("src.agents.sophie.agent.Sandbox")
    @patch("src.agents.sophie.agent.GithubToolKit")
    async def test_tool_kits_initialized(self, mock_github_kit_class, mock_sandbox_class):
        """Test that tool kits are properly initialized."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        mock_sandbox_tools = MagicMock()
        mock_sandbox_tools.as_tool_kits.return_value = {
            "RunCode": AsyncMock(),
            "RunCommand": AsyncMock(),
            "WriteFile": AsyncMock(),
            "ReadFile": AsyncMock(),
            "AppendFile": AsyncMock(),
            "EditFile": AsyncMock(),
            "ListFiles": AsyncMock(),
        }
        
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
                # Check that GitHub tools are present
                assert "FetchFromGithub" in s.tool_kits
                assert "CreateGithubIssue" in s.tool_kits
                assert "PrToGithub" in s.tool_kits


class TestSophieCompact:
    """Test Sophie's context compaction functionality."""

    def test_compact_short_context_unchanged(self):
        """Test that short contexts are not compacted."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        # Create a context with 5 messages (under 12 threshold)
        context = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Assistant 1"},
            {"role": "user", "content": "User 2"},
            {"role": "assistant", "content": "Assistant 2"},
        ]
        
        result = sophie.compact(context)
        assert len(result) == 5
        assert result == context

    def test_compact_long_context_reduced(self):
        """Test that long contexts are compacted."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4",
            max_context=8192,
            github_repo="test/repo",
        )
        
        # Create a context with 15 messages (over 12 threshold)
        context = [{"role": "system", "content": "System"}]
        context.append({"role": "user", "content": "First user"})
        for i in range(13):
            context.append({"role": "assistant", "content": f"Assistant {i}"})
            context.append({"role": "user", "content": f"User {i}"})
        
        result = sophie.compact(context)
        
        # Should have system + first user + last 10 messages
        assert len(result) <= 12
        assert result[0]["role"] == "system"


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
    @patch("src.agents.sophie.agent.Sandbox")
    async def test_sophie_has_sandbox_tools(self, mock_sandbox_class):
        """Test that Sophie has access to sandbox tools."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
            mock_sandbox_tools = MagicMock()
            mock_sandbox_tools.as_tool_kits.return_value = {
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
                # Check sandbox tools
                assert "RunCode" in s.tool_kits
                assert "RunCommand" in s.tool_kits
                assert "WriteFile" in s.tool_kits
                assert "ReadFile" in s.tool_kits
                assert "EditFile" in s.tool_kits
                assert "ListFiles" in s.tool_kits

    @pytest.mark.asyncio
    @patch("src.agents.sophie.agent.Sandbox")
    async def test_sophie_has_github_tools(self, mock_sandbox_class):
        """Test that Sophie has access to GitHub tools."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
            mock_sandbox_tools = MagicMock()
            mock_sandbox_tools.as_tool_kits.return_value = {}
            mock_toolkit_class.return_value = mock_sandbox_tools
            
            sophie = Sophie.create(
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                model="gpt-4",
                max_context=8192,
                github_repo="test/repo",
            )
            
            async with sophie as s:
                # Check GitHub tools
                assert "FetchFromGithub" in s.tool_kits
                assert "CreateGithubIssue" in s.tool_kits
                assert "PrToGithub" in s.tool_kits
                assert "GetIssueComments" in s.tool_kits
                assert "ReplyToIssue" in s.tool_kits
                assert "GetPRReviews" in s.tool_kits
                assert "GetPRReviewComments" in s.tool_kits
                assert "ReplyToPRReviewComment" in s.tool_kits
                assert "GetPRComments" in s.tool_kits
                assert "ReplyToPR" in s.tool_kits
                assert "GetMyOpenPRs" in s.tool_kits
                assert "GetMyIssues" in s.tool_kits
                assert "GetNotifications" in s.tool_kits

    @pytest.mark.asyncio
    @patch("src.agents.sophie.agent.Sandbox")
    async def test_sophie_has_web_tools(self, mock_sandbox_class):
        """Test that Sophie has access to web tools."""
        mock_sandbox = AsyncMock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.__aenter__ = AsyncMock(return_value=mock_sandbox)
        mock_sandbox.__aexit__ = AsyncMock(return_value=None)
        
        with patch("src.agents.sophie.agent.SandboxToolKit") as mock_toolkit_class:
            mock_sandbox_tools = MagicMock()
            mock_sandbox_tools.as_tool_kits.return_value = {}
            mock_toolkit_class.return_value = mock_sandbox_tools
            
            sophie = Sophie.create(
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                model="gpt-4",
                max_context=8192,
                github_repo="test/repo",
            )
            
            async with sophie as s:
                # Check web tools
                assert "WebFetch" in s.tool_kits
                assert "WebSearch" in s.tool_kits
