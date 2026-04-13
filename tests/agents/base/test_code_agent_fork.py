import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.base.agent import BaseAgentStepResult, ModelConfig
from src.agents.base.code_agent import CodeAgent


class DummyCodeAgent(CodeAgent):
    GITHUB_NICKNAME = "Nexus-Test"

    def step(self, current_turn_ctx: list) -> BaseAgentStepResult:
        raise NotImplementedError("unused in these tests")

    def last_report_current_process(self, current_turn_ctx: list) -> str:
        return "unused"


def make_agent() -> DummyCodeAgent:
    with patch("src.agents.base.agent.AsyncOpenAI"):
        return DummyCodeAgent(
            name="dummy-code-agent",
            tool_kits=None,
            base_url="http://localhost",
            api_key="test-key",
            system_prompt="test",
            llm_config=ModelConfig(model="gpt-4o", max_length_context=128_000),
            max_attempts=10,
        )


def make_mock_http_client(mock_client_cls, *, get_status_code: int, post_status_code: int = 202):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=MagicMock(status_code=get_status_code))
    mock_http.post = AsyncMock(return_value=MagicMock(status_code=post_status_code, text="error"))
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_http


def test_ensure_fork_checks_repo_endpoint_without_pinning_api_version():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(mock_client_cls, get_status_code=200)
        fork_repo = asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Test/repo"
    mock_http.get.assert_awaited_once_with(
        "https://api.github.com/repos/Nexus-Test/repo",
        headers={
            "Authorization": "Bearer ghp_test",
            "Accept": "application/vnd.github+json",
        },
    )


def test_ensure_fork_creates_when_missing():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(mock_client_cls, get_status_code=404)
        fork_repo = asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Test/repo"
    mock_http.post.assert_awaited_once_with(
        "https://api.github.com/repos/owner/repo/forks",
        headers={
            "Authorization": "Bearer ghp_test",
            "Accept": "application/vnd.github+json",
        },
    )


def test_ensure_fork_skips_creation_when_exists():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(mock_client_cls, get_status_code=200)
        asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    mock_http.post.assert_not_awaited()

