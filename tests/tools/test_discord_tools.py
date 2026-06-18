from __future__ import annotations

import pytest

from src.extensions.discord import DiscordApiError
from src.tools.discord import DISCORD_TOOL_DEFINITIONS, DiscordTools


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Run anyio tests on asyncio only."""
    return "asyncio"


class FakeDiscordClient:
    def __init__(self) -> None:
        self.created_for: list[str] = []
        self.sent: list[tuple[str, str]] = []

    async def create_dm(self, recipient_id: str) -> str:
        self.created_for.append(recipient_id)
        return "channel-1"

    async def send_message(self, channel_id: str, content: str, embeds=None) -> dict:
        self.sent.append((channel_id, content))
        return {"id": "message-1"}


async def test_send_discord_dm_uses_default_recipient():
    """Verify DM tool creates a channel and sends the message."""
    client = FakeDiscordClient()
    tools = DiscordTools(
        bot_token=None,
        default_recipient_id="user-1",
        client=client,
    )

    result = await tools.send_discord_dm("hello")

    assert result["success"] is True
    assert result["channel_id"] == "channel-1"
    assert result["message_id"] == "message-1"
    assert client.created_for == ["user-1"]
    assert client.sent == [("channel-1", "hello")]


async def test_send_discord_dm_requires_recipient():
    """Verify DM tool fails cleanly without a configured recipient."""
    tools = DiscordTools(bot_token=None, default_recipient_id=None, client=FakeDiscordClient())

    result = await tools.send_discord_dm("hello")

    assert result == {
        "success": False,
        "message": "Discord recipient id is not configured.",
    }


async def test_send_discord_message_reports_api_error():
    """Verify Discord API errors are returned as tool failures."""

    class FailingClient(FakeDiscordClient):
        async def send_message(self, channel_id: str, content: str, embeds=None) -> dict:
            raise DiscordApiError("rate limited")

    tools = DiscordTools(bot_token=None, client=FailingClient())

    result = await tools.send_discord_message("channel-1", "hello")

    assert result == {
        "success": False,
        "message": "rate limited",
    }


def test_discord_tool_definitions_match_toolkit_names():
    """Verify exposed tool schema names match callable names."""
    tool_names = {tool["function"]["name"] for tool in DISCORD_TOOL_DEFINITIONS}
    callable_names = set(DiscordTools(bot_token=None, client=FakeDiscordClient()).all_tools)

    assert tool_names == callable_names
