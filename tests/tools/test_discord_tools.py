from __future__ import annotations

from collections import deque

import anyio
import httpx

import src.tools.discord as discord_tools
from src.tools.discord import (
    DISCORD_TOOLS_SCHEMA,
    DiscordTools,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://discord.com/api/v10/test")
            response = httpx.Response(
                self.status_code,
                json=self._payload,
                request=request,
            )
            raise httpx.HTTPStatusError("Discord API error", request=request, response=response)


class FakeAsyncClient:
    calls: list[dict[str, object]] = []
    responses: deque[FakeResponse] = deque()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.responses.popleft()


def setup_fake_client(monkeypatch, responses: list[FakeResponse]) -> None:
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = deque(responses)
    monkeypatch.setattr(discord_tools.httpx, "AsyncClient", FakeAsyncClient)


def tool_schema_names() -> set[str]:
    return {tool["function"]["name"] for tool in DISCORD_TOOLS_SCHEMA}


def test_discord_tool_schemas_do_not_expose_bot_token() -> None:
    assert tool_schema_names() == {
        "send_discord_dm",
        "send_discord_channel_message",
        "reply_to_discord_channel_message",
    }
    for tool in DISCORD_TOOLS_SCHEMA:
        properties = tool["function"]["parameters"]["properties"]
        assert "token" not in properties
        assert "bot_token" not in properties


def test_send_discord_dm_creates_dm_channel_and_sends_message(monkeypatch) -> None:
    setup_fake_client(
        monkeypatch,
        [
            FakeResponse(200, {"id": "dm-channel"}),
            FakeResponse(200, {"id": "message-1", "channel_id": "dm-channel"}),
        ],
    )

    async def run():
        tools = DiscordTools(bot_token="bot-token")
        return await tools.send_discord_dm(user_id="user-1", content="hello")

    result = anyio.run(run)

    assert result["success"] is True
    assert result["channel_id"] == "dm-channel"
    assert result["message_url"] == "https://discord.com/channels/@me/dm-channel/message-1"
    assert FakeAsyncClient.calls == [
        {
            "url": "https://discord.com/api/v10/users/@me/channels",
            "headers": {
                "Authorization": "Bot bot-token",
                "Content-Type": "application/json",
                "User-Agent": "Nexus Assistant Discord Tools",
            },
            "json": {"recipient_id": "user-1"},
        },
        {
            "url": "https://discord.com/api/v10/channels/dm-channel/messages",
            "headers": {
                "Authorization": "Bot bot-token",
                "Content-Type": "application/json",
                "User-Agent": "Nexus Assistant Discord Tools",
            },
            "json": {"content": "hello"},
        },
    ]


def test_reply_to_discord_channel_message_uses_message_reference(monkeypatch) -> None:
    setup_fake_client(
        monkeypatch,
        [
            FakeResponse(
                200,
                {
                    "id": "reply-1",
                    "channel_id": "channel-1",
                    "guild_id": "guild-1",
                },
            ),
        ],
    )

    async def run():
        tools = DiscordTools(bot_token="bot-token")
        return await tools.reply_to_discord_channel_message(
            channel_id="channel-1",
            message_id="message-1",
            content="ack",
        )

    result = anyio.run(run)

    assert result["success"] is True
    assert result["reply_to_message_id"] == "message-1"
    assert result["message_url"] == "https://discord.com/channels/guild-1/channel-1/reply-1"
    assert FakeAsyncClient.calls[0]["json"] == {
        "content": "ack",
        "message_reference": {
            "channel_id": "channel-1",
            "message_id": "message-1",
        },
        "allowed_mentions": {
            "parse": [],
            "replied_user": False,
        },
    }


def test_send_discord_channel_message_reports_api_error(monkeypatch) -> None:
    setup_fake_client(
        monkeypatch,
        [FakeResponse(403, {"message": "Missing Permissions"})],
    )

    async def run():
        tools = DiscordTools(bot_token="bot-token")
        return await tools.send_discord_channel_message(
            channel_id="channel-1",
            content="hello",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Discord API error 403: Missing Permissions",
    }


def test_discord_tools_report_missing_bot_token_without_http_call() -> None:
    async def run():
        tools = DiscordTools(bot_token=None)
        return await tools.send_discord_channel_message(
            channel_id="channel-1",
            content="hello",
        )

    result = anyio.run(run)

    assert result == {
        "success": False,
        "message": "Discord bot token is not configured.",
    }
