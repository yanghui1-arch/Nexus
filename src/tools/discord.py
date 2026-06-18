from __future__ import annotations

from typing import Callable

from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field

from src.extensions.discord import DiscordApiError, DiscordRestClient


class SendDiscordDM(BaseModel):
    """Send a direct message through the configured Discord bot."""

    content: str = Field(description="Message content to send")
    recipient_id: str | None = Field(
        default=None,
        description="Optional Discord user id. Uses the configured default recipient when omitted.",
    )


class SendDiscordMessage(BaseModel):
    """Send a message to a Discord channel through the configured bot."""

    channel_id: str = Field(description="Discord channel id")
    content: str = Field(description="Message content to send")


SEND_DISCORD_DM = pydantic_function_tool(SendDiscordDM, name="send_discord_dm")
SEND_DISCORD_MESSAGE = pydantic_function_tool(SendDiscordMessage, name="send_discord_message")

DISCORD_TOOL_DEFINITIONS = [
    SEND_DISCORD_DM,
    SEND_DISCORD_MESSAGE,
]


class DiscordTools:
    """Discord tools bound to configured bot credentials."""

    def __init__(
        self,
        *,
        bot_token: str | None,
        default_recipient_id: str | None = None,
        client: DiscordRestClient | None = None,
    ) -> None:
        """Initialize the toolkit."""
        self._bot_token = bot_token
        self._default_recipient_id = default_recipient_id
        self._client = client

    def _get_client(self) -> DiscordRestClient:
        if self._client is not None:
            return self._client
        if not self._bot_token:
            raise RuntimeError("Discord bot token is not configured.")
        self._client = DiscordRestClient(self._bot_token)
        return self._client

    @track(step_type="tool")
    async def send_discord_dm(
        self,
        content: str,
        recipient_id: str | None = None,
    ) -> dict:
        """Send a DM to the configured Discord user."""
        target_id = recipient_id or self._default_recipient_id
        if not target_id:
            return {
                "success": False,
                "message": "Discord recipient id is not configured.",
            }
        try:
            client = self._get_client()
            channel_id = await client.create_dm(target_id)
            message = await client.send_message(channel_id, content)
        except (DiscordApiError, RuntimeError, ValueError) as exc:
            return {
                "success": False,
                "message": str(exc),
            }
        return {
            "success": True,
            "channel_id": channel_id,
            "message_id": message.get("id"),
            "message": "Discord DM sent.",
        }

    @track(step_type="tool")
    async def send_discord_message(
        self,
        channel_id: str,
        content: str,
    ) -> dict:
        """Send a message to a Discord channel."""
        try:
            client = self._get_client()
            message = await client.send_message(channel_id, content)
        except (DiscordApiError, RuntimeError, ValueError) as exc:
            return {
                "success": False,
                "message": str(exc),
            }
        return {
            "success": True,
            "channel_id": channel_id,
            "message_id": message.get("id"),
            "message": "Discord message sent.",
        }

    @property
    def all_tools(self) -> dict[str, Callable]:
        """Return Discord tools exposed to agents."""
        return {
            "send_discord_dm": self.send_discord_dm,
            "send_discord_message": self.send_discord_message,
        }
