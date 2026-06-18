from __future__ import annotations

import httpx
import pytest

from src.extensions.discord.client import DISCORD_MESSAGE_LIMIT, DiscordRestClient


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Run anyio tests on asyncio only."""
    return "asyncio"


class FakeAsyncClient:
    responses: list[httpx.Response] = []
    requests: list[dict[str, object]] = []

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    """Patch Discord HTTP calls."""
    FakeAsyncClient.responses = []
    FakeAsyncClient.requests = []
    monkeypatch.setattr("src.extensions.discord.client.httpx.AsyncClient", FakeAsyncClient)


async def test_discord_create_dm_and_fetch_messages():
    """Verify Discord create DM and message parsing."""
    FakeAsyncClient.responses = [
        httpx.Response(200, json={"id": "channel-1"}),
        httpx.Response(
            200,
            json=[
                {
                    "id": "101",
                    "channel_id": "channel-1",
                    "content": "review owner/repo#1",
                    "author": {"id": "user-1"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ],
        ),
    ]

    client = DiscordRestClient("token")
    channel_id = await client.create_dm("user-1")
    messages = await client.fetch_messages(channel_id, after="100")

    assert channel_id == "channel-1"
    assert messages[0].content == "review owner/repo#1"
    assert FakeAsyncClient.requests[1]["params"]["after"] == "100"


async def test_discord_send_message_truncates_and_disables_mentions():
    """Verify outbound messages are bounded and do not ping users."""
    FakeAsyncClient.responses = [httpx.Response(200, json={"id": "message-1"})]
    client = DiscordRestClient("token")

    await client.send_message("channel-1", "x" * (DISCORD_MESSAGE_LIMIT + 20))

    payload = FakeAsyncClient.requests[0]["json"]
    assert len(payload["content"]) == DISCORD_MESSAGE_LIMIT
    assert payload["content"].endswith("...")
    assert payload["allowed_mentions"] == {"parse": []}


async def test_discord_retries_rate_limit(monkeypatch):
    """Verify Discord 429 retry handling."""
    sleeps: list[float] = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("src.extensions.discord.client.asyncio.sleep", fake_sleep)
    FakeAsyncClient.responses = [
        httpx.Response(429, json={"retry_after": 0.01}),
        httpx.Response(200, json={"id": "message-1"}),
    ]
    client = DiscordRestClient("token")

    await client.send_message("channel-1", "hello")

    assert len(FakeAsyncClient.requests) == 2
    assert sleeps == [0.01]
