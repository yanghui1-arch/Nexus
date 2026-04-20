import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def make_response(status_code: int, payload: dict | None = None, text: str = "error"):
    response = MagicMock(status_code=status_code, text=text)
    response.json = MagicMock(return_value=payload or {})
    return response


def make_mock_http_client(mock_client_cls, *, get_responses: list[MagicMock], post_response=None):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=get_responses)
    mock_http.post = AsyncMock(return_value=post_response or make_response(202, text="accepted"))
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_http


def test_ensure_fork_checks_repo_endpoint_without_pinning_api_version():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(
            mock_client_cls,
            get_responses=[
                make_response(
                    200,
                    payload={"fork": True, "parent": {"full_name": "owner/repo"}},
                )
            ],
        )
        fork_repo = asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Test/repo"
    mock_http.get.assert_awaited_once_with(
        "https://api.github.com/repos/Nexus-Test/repo",
        headers={
            "Authorization": "Bearer ghp_test",
            "Accept": "application/vnd.github+json",
        },
    )


def test_ensure_fork_creates_when_missing_and_waits_until_ready():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(
            mock_client_cls,
            get_responses=[
                make_response(404),
                make_response(404),
                make_response(
                    200,
                    payload={"fork": True, "parent": {"full_name": "owner/repo"}},
                ),
            ],
            post_response=make_response(202, text="accepted"),
        )
        with patch("src.agents.base.code_agent.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            fork_repo = asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Test/repo"
    assert mock_http.get.await_count == 3
    mock_http.post.assert_awaited_once_with(
        "https://api.github.com/repos/owner/repo/forks",
        headers={
            "Authorization": "Bearer ghp_test",
            "Accept": "application/vnd.github+json",
        },
    )
    mock_sleep.assert_awaited_once()


def test_ensure_fork_skips_creation_when_exists():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(
            mock_client_cls,
            get_responses=[
                make_response(
                    200,
                    payload={"fork": True, "parent": {"full_name": "owner/repo"}},
                )
            ],
        )
        asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    mock_http.post.assert_not_awaited()


def test_ensure_fork_rejects_repo_that_points_to_different_upstream():
    agent = make_agent()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        make_mock_http_client(
            mock_client_cls,
            get_responses=[
                make_response(
                    200,
                    payload={"fork": True, "parent": {"full_name": "someone-else/repo"}},
                )
            ],
        )

        with pytest.raises(RuntimeError, match="expected owner/repo"):
            asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))


def test_ensure_fork_times_out_when_github_never_exposes_the_fork():
    agent = make_agent()
    original_timeout = DummyCodeAgent.FORK_READY_TIMEOUT_SECONDS
    DummyCodeAgent.FORK_READY_TIMEOUT_SECONDS = 0

    try:
        with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
            make_mock_http_client(
                mock_client_cls,
                get_responses=[make_response(404), make_response(404)],
                post_response=make_response(202, text="accepted"),
            )

            with pytest.raises(TimeoutError, match="never became ready"):
                asyncio.run(agent._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))
    finally:
        DummyCodeAgent.FORK_READY_TIMEOUT_SECONDS = original_timeout

