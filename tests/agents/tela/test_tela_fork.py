import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from src.agents.base.agent import ModelConfig
from src.agents.tela import Tela


def make_tela() -> Tela:
    with patch("src.agents.base.agent.AsyncOpenAI"):
        return Tela(
            name="Tela",
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


def test_ensure_fork_checks_tela_fork_repo_endpoint():
    tela = make_tela()

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
        fork_repo = asyncio.run(tela._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Tela/repo"
    mock_http.get.assert_awaited_once_with(
        "https://api.github.com/repos/Nexus-Tela/repo",
        headers=ANY,
    )
    headers = mock_http.get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer ghp_test"
    assert headers["Accept"] == "application/vnd.github+json"


def test_ensure_fork_creates_tela_fork_when_missing():
    tela = make_tela()

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
        fork_repo = asyncio.run(tela._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    assert fork_repo == "Nexus-Tela/repo"
    assert mock_http.get.await_count == 2
    mock_http.post.assert_awaited_once_with(
        "https://api.github.com/repos/owner/repo/forks",
        headers=ANY,
    )


def test_ensure_fork_skips_creation_when_tela_fork_exists():
    tela = make_tela()

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
        asyncio.run(tela._ensure_fork(token="ghp_test", upstream_repo="owner/repo"))

    mock_http.post.assert_not_awaited()
