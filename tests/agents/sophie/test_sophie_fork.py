import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from src.agents.base.agent import ModelConfig
from src.agents.sophie import Sophie


def make_sophie() -> Sophie:
    with patch("src.agents.base.agent.AsyncOpenAI"):
        return Sophie(
            name="Sophie",
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


def test_ensure_fork_checks_sophie_fork_repo_endpoint():
    sophie = make_sophie()

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
        fork_repo = asyncio.run(sophie._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Sophie/repo"
    mock_http.get.assert_awaited_once_with(
        "https://api.github.com/repos/Nexus-Sophie/repo",
        headers=ANY,
    )
    headers = mock_http.get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer ghp_test"
    assert headers["Accept"] == "application/vnd.github+json"


def test_ensure_fork_creates_sophie_fork_when_missing():
    sophie = make_sophie()

    with patch("src.agents.base.code_agent.httpx.AsyncClient") as mock_client_cls:
        mock_http = make_mock_http_client(
            mock_client_cls,
            get_responses=[
                make_response(404),
                make_response(
                    200,
                    payload={"fork": True, "parent": {"full_name": "owner/repo"}},
                ),
            ],
            post_response=make_response(202, text="accepted"),
        )
        fork_repo = asyncio.run(sophie._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Sophie/repo"
    assert mock_http.get.await_count == 2
    mock_http.post.assert_awaited_once_with(
        "https://api.github.com/repos/owner/repo/forks",
        headers=ANY,
    )


def test_ensure_fork_skips_creation_when_sophie_fork_exists():
    sophie = make_sophie()

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
        asyncio.run(sophie._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    mock_http.post.assert_not_awaited()
