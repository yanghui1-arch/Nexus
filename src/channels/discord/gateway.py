from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import discord

from src.logger import logger
from src.server.config import Settings
from src.server.services.background import BackgroundService


@dataclass(frozen=True)
class DiscordMessageEvent:
    """Message data passed from the Discord Gateway to Nexus handlers."""

    message_id: str
    channel_id: str
    channel_name: str | None
    parent_channel_id: str | None
    guild_id: str | None
    guild_name: str | None
    author_id: str
    author_name: str | None
    content: str
    is_direct_message: bool
    mentions_bot: bool


class DiscordMessageHandler(Protocol):
    async def handle_message(self, event: DiscordMessageEvent) -> None:
        ...


class DiscordGateway(BackgroundService):
    """Discord realtime Gateway listener.

    The websocket lifecycle, heartbeat, reconnect, and resume behavior are owned by
    discord.py. This class only maps Nexus settings into gateway intents, filters
    messages, and emits normalized message events.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        handler: DiscordMessageHandler,
    ) -> None:
        if handler is None:
            raise ValueError("DiscordGateway requires a DiscordMessageHandler.")
        self._settings = settings
        self._handler = handler
        self._allowed_channel_ids = set(settings.discord_gateway_channel_ids)
        self._allowed_user_ids = set(settings.discord_gateway_user_ids)
        self._client: discord.Client | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._settings.discord_gateway_enabled and self._settings.discord_gateway_bot_token)

    def start(self) -> None:
        if not self.enabled:
            logger.info("Discord Gateway is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="nexus-discord-gateway")
        logger.info("Discord Gateway starts.")

    async def stop(self) -> None:
        if self._client is not None and not self._client.is_closed():
            await self._client.close()
        if self._task is None:
            return
        await self._task
        self._task = None
        logger.info("Discord Gateway stops.")

    async def _run(self) -> None:
        client = discord.Client(intents=_message_intents())
        self._client = client

        @client.event
        async def on_ready() -> None:
            logger.info("Discord Gateway is ready as %s.", client.user)

        @client.event
        async def on_message(message: discord.Message) -> None:
            await self._handle_raw_message(message, bot_user=client.user)

        token = self._settings.discord_gateway_bot_token
        if not token:
            logger.info("Discord Gateway token is not configured.")
            return
        try:
            await client.start(token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Discord Gateway listener failed.")
            raise

    async def _handle_raw_message(
        self,
        message: discord.Message,
        *,
        bot_user: discord.abc.User | None,
    ) -> None:
        event = _message_event(message, bot_user=bot_user)
        if event is None or not self._should_emit(event):
            return
        try:
            await self._handler.handle_message(event)
        except Exception:
            logger.exception("Discord Gateway message handler failed for message %s.", event.message_id)

    def _should_emit(self, event: DiscordMessageEvent) -> bool:
        if self._allowed_user_ids and event.author_id not in self._allowed_user_ids:
            return False
        if event.is_direct_message:
            return True
        if not self._allowed_channel_ids:
            return False
        return event.channel_id in self._allowed_channel_ids or (
            event.parent_channel_id is not None and event.parent_channel_id in self._allowed_channel_ids
        )


def _message_intents() -> discord.Intents:
    """Build the minimal intents for DM and guild message delivery."""
    intents = discord.Intents.none()
    intents.guilds = True
    intents.dm_messages = True
    intents.guild_messages = True
    intents.message_content = True
    return intents


def _message_event(
    message: discord.Message,
    *,
    bot_user: discord.abc.User | None,
) -> DiscordMessageEvent | None:
    author = message.author
    if author.bot:
        return None

    bot_user_id = str(bot_user.id) if bot_user is not None else None
    author_id = str(author.id)
    if bot_user_id is not None and author_id == bot_user_id:
        return None

    channel = message.channel
    guild = message.guild
    channel_id = str(channel.id)
    channel_name, parent_channel_id = _channel_metadata(channel)

    return DiscordMessageEvent(
        message_id=str(message.id),
        channel_id=channel_id,
        channel_name=channel_name,
        parent_channel_id=parent_channel_id,
        guild_id=str(guild.id) if guild is not None else None,
        guild_name=guild.name if guild is not None else None,
        author_id=author_id,
        author_name=author.name,
        content=message.content,
        is_direct_message=guild is None,
        mentions_bot=bot_user_id is not None and any(str(user.id) == bot_user_id for user in message.mentions),
    )


def _channel_metadata(channel: discord.abc.Messageable) -> tuple[str | None, str | None]:
    """Return (channel_name, parent_channel_id) for message channels."""
    if isinstance(channel, discord.DMChannel):
        return None, None
    if isinstance(channel, discord.Thread):
        return channel.name, str(channel.parent_id) if channel.parent_id is not None else None
    if isinstance(channel, discord.GroupChannel):
        return channel.name, None
    if isinstance(channel, discord.abc.GuildChannel):
        return channel.name, None
    return None, None


def _preview(value: str, *, limit: int = 200) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
