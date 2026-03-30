"""Tests for Sophie agent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.agents.sophie import Sophie
from src.agents.sophie.system_prompt import SOPHIE_SYSTEM_PROMPT


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox."""
    sandbox = Mock()
    sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "exists", "stderr": ""})
    sandbox.__aenter__ = AsyncMock(return_value=sandbox)
    sandbox.__aexit__ = AsyncMock(return_value=None)
    return sandbox


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    client = Mock()
    mock_completion = Mock()
    mock_completion.choices = [Mock(finish_reason="stop", message=Mock(content="Done", tool_calls=None))]
    mock_completion.usage = Mock(total_tokens=100)
    client.chat.completions.create = Mock(return_value=mock_completion)
    return client


class TestSophie:
    """Test suite for Sophie agent."""

    def test_create_factory(self):
        """Test the create factory method."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        assert sophie.name == "Sophie"
        assert sophie.system_prompt == SOPHIE_SYSTEM_PROMPT
        assert sophie.llm_config.model == "gpt-4o"
        assert sophie.llm_config.max_length_context == 128000

    def test_create_with_github(self):
        """Test creation with GitHub configuration."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
            github_repo="owner/repo",
            github_token="ghp_token",
        )
        
        assert sophie.github_repo == "owner/repo"
        assert sophie.github_token == "ghp_token"

    @pytest.mark.asyncio
    async def test_sophie_context_manager(self, mock_sandbox):
        """Test Sophie as async context manager."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        with patch("src.agents.sophie.agent.Sandbox", return_value=mock_sandbox):
            async with sophie as s:
                assert s._sandbox is not None
                assert s.tool_kits is not None
                # Verify GitHub tools are registered
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
                # Verify web tools
                assert "WebFetch" in s.tool_kits
                assert "WebSearch" in s.tool_kits

    @pytest.mark.asyncio
    async def test_system_prompt_includes_design_principles(self):
        """Verify system prompt includes Anthropic design principles."""
        assert "Clarity" in SOPHIE_SYSTEM_PROMPT
        assert "Craft" in SOPHIE_SYSTEM_PROMPT
        assert "Trust" in SOPHIE_SYSTEM_PROMPT
        assert "Thoughtfulness" in SOPHIE_SYSTEM_PROMPT
        assert "Human-centered" in SOPHIE_SYSTEM_PROMPT
        
        # Verify React expertise
        assert "React" in SOPHIE_SYSTEM_PROMPT
        assert "TypeScript" in SOPHIE_SYSTEM_PROMPT
        assert "accessibility" in SOPHIE_SYSTEM_PROMPT.lower()

    @pytest.mark.asyncio
    async def test_step_requires_context_manager(self):
        """Test that step raises error if not used as context manager."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        with pytest.raises(RuntimeError, match="async context manager"):
            sophie.step([])

    def test_compact_keeps_system_and_recent(self):
        """Test compact keeps system message and recent messages."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        # Create a context with system + 15 messages
        ctx = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "First user message"},
        ]
        for i in range(13):
            ctx.append({"role": "assistant" if i % 2 == 0 else "user", "content": f"Message {i}"})
        
        compacted = sophie.compact(ctx)
        
        # Should keep system + first user + last 10
        assert len(compacted) == 12
        assert compacted[0]["role"] == "system"
        assert compacted[1]["role"] == "user"  # First user message

    def test_last_report_finds_assistant_content(self):
        """Test last_report_current_process finds assistant content."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        ctx = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Final response"},
        ]
        
        result = sophie.last_report_current_process(ctx)
        assert result == "Final response"

    def test_last_report_no_assistant(self):
        """Test last_report_current_process when no assistant message."""
        sophie = Sophie.create(
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model="gpt-4o",
            max_context=128000,
        )
        
        ctx = [{"role": "user", "content": "Question"}]
        
        result = sophie.last_report_current_process(ctx)
        assert "maximum number of attempts" in result
