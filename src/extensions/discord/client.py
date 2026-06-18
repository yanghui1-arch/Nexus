from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_MESSAGE_LIMIT = 2000


class DiscordApiError(RuntimeError):
    """Raised when Discord returns a non-retryable API error."""


@dataclass(frozen=True)
class DiscordMessage:
    id: str
    channel_id: str
    author_id: str | None
    content: str
    timestamp: str | None = None


class DiscordRestClient:
    """Small Discord REST client for DM delivery and command polling."""

    def __init__(
        self,
        bot_token: str,
        *,
        base_url: str = DISCORD_API_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        """Initialize the client."""
        if not bot_token:
            raise ValueError("Discord bot token is required.")
        self._bot_token = bot_token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    async def create_dm(self, recipient_id: str) -> str:
        """Create or return a DM channel for a Discord user."""
        payload = await self._request(
            "POST",
            "/users/@me/channels",
            json={"recipient_id": recipient_id},
        )
        channel_id = payload.get("id") if isinstance(payload, dict) else None
        if not channel_id:
            raise DiscordApiError("Discord create DM response did not include a channel id.")
        return str(channel_id)

    async def send_message(
        self,
        channel_id: str,
        content: str,
        embeds: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a Discord channel."""
        payload: dict[str, Any] = {
            "content": _truncate_content(content),
            "allowed_mentions": {"parse": []},
        }
        if embeds:
            payload["embeds"] = embeds
        response = await self._request("POST", f"/channels/{channel_id}/messages", json=payload)
        return response if isinstance(response, dict) else {}

    async def fetch_messages(
        self,
        channel_id: str,
        *,
        after: str | None = None,
        limit: int = 50,
    ) -> list[DiscordMessage]:
        """Fetch recent messages from a DM channel."""
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if after:
            params["after"] = after
        payload = await self._request("GET", f"/channels/{channel_id}/messages", params=params)
        if not isinstance(payload, list):
            raise DiscordApiError("Discord messages response was not a list.")
        return [_format_message(item) for item in payload]

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Perform one Discord API request with bounded 429 retry handling."""
        headers = {
            "Authorization": f"Bot {self._bot_token}",
            "User-Agent": "Nexus-Discord-Secretary/1.0",
        }
        retry = 0
        while True:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    **kwargs,
                )

            if response.status_code != 429:
                break

            if retry >= self._max_retries:
                break
            retry += 1
            await asyncio.sleep(_retry_after_seconds(response))

        if 200 <= response.status_code < 300:
            if not response.content:
                return {}
            return response.json()

        raise DiscordApiError(
            f"Discord API error {response.status_code}: {_discord_error_message(response)}"
        )


def _truncate_content(content: str) -> str:
    """Return content that fits Discord's message limit."""
    value = content or ""
    if len(value) <= DISCORD_MESSAGE_LIMIT:
        return value
    return value[: DISCORD_MESSAGE_LIMIT - 3] + "..."


def _retry_after_seconds(response: httpx.Response) -> float:
    """Extract Discord retry delay."""
    try:
        payload = response.json()
    except Exception:
        payload = {}
    retry_after = payload.get("retry_after") if isinstance(payload, dict) else None
    if retry_after is None:
        retry_after = response.headers.get("retry-after")
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return 1.0


def _discord_error_message(response: httpx.Response) -> str:
    """Extract a readable Discord error message."""
    try:
        payload = response.json()
    except Exception:
        return response.text
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return response.text


def _format_message(payload: dict[str, Any]) -> DiscordMessage:
    """Format a Discord message payload."""
    author = payload.get("author")
    author_id = author.get("id") if isinstance(author, dict) else None
    return DiscordMessage(
        id=str(payload.get("id", "")),
        channel_id=str(payload.get("channel_id", "")),
        author_id=str(author_id) if author_id is not None else None,
        content=str(payload.get("content") or ""),
        timestamp=payload.get("timestamp"),
    )
