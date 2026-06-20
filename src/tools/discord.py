from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
from mwin import track
from openai import pydantic_function_tool
from pydantic import BaseModel, Field


DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_MESSAGE_LIMIT = 2000
DiscordToolCallable = Callable[..., Awaitable[dict[str, object]]]


class SendDiscordDM(BaseModel):
    """Send a direct message to one Discord user."""

    user_id: str = Field(description="Discord user ID to receive the direct message")
    content: str = Field(
        min_length=1,
        max_length=DISCORD_MESSAGE_LIMIT,
        description="Message body to send. Discord messages are limited to 2000 characters.",
    )


class SendDiscordChannelMessage(BaseModel):
    """Send a message to a Discord channel."""

    channel_id: str = Field(description="Discord channel ID to send the message to")
    content: str = Field(
        min_length=1,
        max_length=DISCORD_MESSAGE_LIMIT,
        description="Message body to send. Discord messages are limited to 2000 characters.",
    )


class ReplyToDiscordChannelMessage(BaseModel):
    """Reply to an existing message in a Discord channel."""

    channel_id: str = Field(description="Discord channel ID containing the message")
    message_id: str = Field(description="Discord message ID to reply to")
    content: str = Field(
        min_length=1,
        max_length=DISCORD_MESSAGE_LIMIT,
        description="Reply body to send. Discord messages are limited to 2000 characters.",
    )


SEND_DISCORD_DM = pydantic_function_tool(SendDiscordDM, name="send_discord_dm")
SEND_DISCORD_CHANNEL_MESSAGE = pydantic_function_tool(
    SendDiscordChannelMessage,
    name="send_discord_channel_message",
)
REPLY_TO_DISCORD_CHANNEL_MESSAGE = pydantic_function_tool(
    ReplyToDiscordChannelMessage,
    name="reply_to_discord_channel_message",
)
DISCORD_TOOLS_SCHEMA = [
    SEND_DISCORD_DM,
    SEND_DISCORD_CHANNEL_MESSAGE,
    REPLY_TO_DISCORD_CHANNEL_MESSAGE,
]


class DiscordTools:
    """Discord REST tools bound to one bot token.

    The token is stored on the toolkit instance instead of exposed as a tool
    parameter, so the model can send messages without seeing the bot secret.
    """

    def __init__(self, *, bot_token: str | None, base_url: str = DISCORD_API_BASE_URL) -> None:
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")

    @property
    def all_tools(self) -> dict[str, DiscordToolCallable]:
        return {
            "send_discord_dm": self.send_discord_dm,
            "send_discord_channel_message": self.send_discord_channel_message,
            "reply_to_discord_channel_message": self.reply_to_discord_channel_message,
        }

    @track(step_type="tool")
    async def send_discord_dm(self, user_id: str, content: str) -> dict[str, object]:
        """Send a Discord direct message to a user."""
        if not self._bot_token:
            return _missing_token_result()

        async with httpx.AsyncClient() as client:
            try:
                channel_response = await client.post(
                    f"{self._base_url}/users/@me/channels",
                    headers=_discord_headers(self._bot_token),
                    json={"recipient_id": user_id},
                )
                channel_response.raise_for_status()
                channel = channel_response.json()
                channel_id = str(channel["id"])

                message = await self._send_channel_message(
                    client=client,
                    channel_id=channel_id,
                    payload={"content": content},
                )
                return {
                    "success": True,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "message_id": message["id"],
                    "message_url": _discord_message_url(message),
                    "message": "Discord direct message sent.",
                }
            except httpx.HTTPStatusError as exc:
                return _discord_http_error_result(exc)
            except httpx.HTTPError as exc:
                return _discord_request_error_result(exc)

    @track(step_type="tool")
    async def send_discord_channel_message(self, channel_id: str, content: str) -> dict[str, object]:
        """Send a message to a Discord channel."""
        if not self._bot_token:
            return _missing_token_result()

        async with httpx.AsyncClient() as client:
            try:
                message = await self._send_channel_message(
                    client=client,
                    channel_id=channel_id,
                    payload={"content": content},
                )
                return {
                    "success": True,
                    "channel_id": channel_id,
                    "message_id": message["id"],
                    "message_url": _discord_message_url(message),
                    "message": "Discord channel message sent.",
                }
            except httpx.HTTPStatusError as exc:
                return _discord_http_error_result(exc)
            except httpx.HTTPError as exc:
                return _discord_request_error_result(exc)

    @track(step_type="tool")
    async def reply_to_discord_channel_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> dict[str, object]:
        """Reply to a Discord channel message without pinging the original author."""
        if not self._bot_token:
            return _missing_token_result()

        async with httpx.AsyncClient() as client:
            try:
                message = await self._send_channel_message(
                    client=client,
                    channel_id=channel_id,
                    payload={
                        "content": content,
                        "message_reference": {
                            "channel_id": channel_id,
                            "message_id": message_id,
                        },
                        "allowed_mentions": {
                            "parse": [],
                            "replied_user": False,
                        },
                    },
                )
                return {
                    "success": True,
                    "channel_id": channel_id,
                    "reply_to_message_id": message_id,
                    "message_id": message["id"],
                    "message_url": _discord_message_url(message),
                    "message": "Discord channel reply sent.",
                }
            except httpx.HTTPStatusError as exc:
                return _discord_http_error_result(exc)
            except httpx.HTTPError as exc:
                return _discord_request_error_result(exc)

    async def _send_channel_message(
        self,
        *,
        client: httpx.AsyncClient,
        channel_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        response = await client.post(
            f"{self._base_url}/channels/{channel_id}/messages",
            headers=_discord_headers(self._bot_token or ""),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return {str(key): value for key, value in data.items()}


def _discord_headers(bot_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
        "User-Agent": "Nexus Assistant Discord Tools",
    }


def _discord_message_url(message: dict[str, object]) -> str:
    message_id = str(message["id"])
    channel_id = str(message["channel_id"])
    guild_id = message.get("guild_id")
    guild_path = str(guild_id) if guild_id else "@me"
    return f"https://discord.com/channels/{guild_path}/{channel_id}/{message_id}"


def _discord_http_error_result(exc: httpx.HTTPStatusError) -> dict[str, object]:
    return {
        "success": False,
        "message": f"Discord API error {exc.response.status_code}: {_discord_error_detail(exc.response)}",
    }


def _discord_request_error_result(exc: httpx.HTTPError) -> dict[str, object]:
    return {
        "success": False,
        "message": f"Discord request failed: {exc}",
    }


def _discord_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return response.text


def _missing_token_result() -> dict[str, object]:
    return {
        "success": False,
        "message": "Discord bot token is not configured.",
    }
