from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import discord
import pytest

from src.channels.discord import DiscordGateway, DiscordMessageEvent
from src.server.config import Settings


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio tests on asyncio only."""
    return "asyncio"


class CapturingHandler:
    def __init__(self) -> None:
        self.events: list[DiscordMessageEvent] = []

    async def handle_message(self, event: DiscordMessageEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class FakeDiscordUser:
    id: str
    name: str
    bot: bool = False


@dataclass(frozen=True)
class FakeDiscordChannel:
    id: str
    name: str


@dataclass(frozen=True)
class FakeDiscordGuild:
    id: str
    name: str


@dataclass(frozen=True)
class FakeDiscordMessage:
    id: str = "msg-1"
    channel: FakeDiscordChannel = field(default_factory=lambda: FakeDiscordChannel("dm-channel", "dm"))
    guild: FakeDiscordGuild | None = None
    author: FakeDiscordUser = field(default_factory=lambda: make_user("user-1"))
    content: str = "hello"
    mentions: list[FakeDiscordUser] = field(default_factory=list)


def settings(
    *,
    discord_gateway_channel_ids: list[str] | None = None,
    discord_gateway_user_ids: list[str] | None = None,
) -> Settings:
    """Build Settings with Discord Gateway fields varied for tests."""
    return Settings(
        api_key=None,
        base_url="https://api.example.com/v1",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_tokens={},
        database_url="postgresql://example",
        redis_url="redis://localhost:6379/0",
        redis_message_ttl_seconds=86400,
        celery_broker_url="redis://localhost:6379/0",
        celery_result_backend="redis://localhost:6379/0",
        celery_queue="nexus_agent_tasks",
        celery_visibility_timeout_seconds=86400,
        celery_task_publish_max_retries=3,
        celery_broker_connection_timeout_seconds=2.0,
        github_feedback_poll_interval_seconds=60,
        github_feedback_poll_task_limit=100,
        github_feedback_batch_size=20,
        github_feedback_http_timeout_seconds=10.0,
        github_oauth_client_id=None,
        github_oauth_client_secret=None,
        github_oauth_redirect_uri="http://localhost:8000/v1/auth/github/callback",
        auth_session_cookie_name="nexus_session",
        auth_session_ttl_seconds=2592000,
        frontend_base_url="http://localhost:5174",
        discord_gateway_enabled=True,
        discord_gateway_bot_token="discord-token",
        discord_gateway_channel_ids=discord_gateway_channel_ids or [],
        discord_gateway_user_ids=discord_gateway_user_ids or [],
        product_discovery_poll_interval_seconds=3600,
        product_discovery_poll_task_limit=100,
        product_discovery_recent_proposal_limit=5,
        product_discovery_pending_proposal_limit=50,
        product_workflow_poll_interval_seconds=60,
        assistant_enabled=True,
        assistant_github_token="assistant-token",
        assistant_poll_interval_seconds=120,
        assistant_merge_method="squash",
        assistant_test_commands={},
    )


def make_user(user_id: str, *, bot: bool = False) -> FakeDiscordUser:
    """Build a fake Discord user object."""
    return FakeDiscordUser(id=user_id, name=f"user-{user_id}", bot=bot)


def make_channel(channel_id: str, *, name: str = "channel") -> FakeDiscordChannel:
    """Build a fake Discord channel object."""
    return FakeDiscordChannel(id=channel_id, name=name)


def make_guild(guild_id: str) -> FakeDiscordGuild:
    """Build a fake Discord guild object."""
    return FakeDiscordGuild(id=guild_id, name=f"guild-{guild_id}")


def make_message(
    *,
    message_id: str = "msg-1",
    channel: FakeDiscordChannel | None = None,
    guild: FakeDiscordGuild | None = None,
    author: FakeDiscordUser | None = None,
    content: str = "hello",
    mentions: list[FakeDiscordUser] | None = None,
) -> discord.Message:
    """Build a fake object shaped like discord.Message for normalization tests."""
    return cast(
        discord.Message,
        FakeDiscordMessage(
            id=message_id,
            channel=channel or make_channel("dm-channel"),
            guild=guild,
            author=author or make_user("user-1"),
            content=content,
            mentions=mentions or [],
        ),
    )


def bot_user() -> discord.abc.User:
    """Build a fake bot user typed as discord.py's user protocol."""
    return cast(discord.abc.User, make_user("bot-user", bot=True))


def test_discord_gateway_requires_explicit_handler() -> None:
    """Verify production cannot silently fall back to logging-only handling."""
    with pytest.raises(TypeError):
        DiscordGateway(settings=settings())  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="requires a DiscordMessageHandler"):
        DiscordGateway(settings=settings(), handler=None)  # type: ignore[arg-type]


async def test_discord_gateway_emits_direct_messages() -> None:
    """Verify DM messages are normalized and emitted."""
    handler = CapturingHandler()
    gateway = DiscordGateway(settings=settings(), handler=handler)

    await gateway._handle_raw_message(make_message(content="hello dm"), bot_user=bot_user())

    assert len(handler.events) == 1
    event = handler.events[0]
    assert event.is_direct_message is True
    assert event.guild_id is None
    assert event.channel_id == "dm-channel"
    assert event.author_id == "user-1"
    assert event.content == "hello dm"


async def test_discord_gateway_emits_configured_guild_channels() -> None:
    """Verify guild messages are limited to configured channels."""
    handler = CapturingHandler()
    gateway = DiscordGateway(
        settings=settings(discord_gateway_channel_ids=["channel-1"]),
        handler=handler,
    )

    await gateway._handle_raw_message(
        make_message(
            channel=make_channel("channel-1"),
            guild=make_guild("guild-1"),
            content="hello channel",
        ),
        bot_user=bot_user(),
    )
    await gateway._handle_raw_message(
        make_message(
            channel=make_channel("channel-2"),
            guild=make_guild("guild-1"),
            content="ignored",
        ),
        bot_user=bot_user(),
    )

    assert [event.content for event in handler.events] == ["hello channel"]


def test_discord_gateway_accepts_thread_parent_channel_events() -> None:
    """Verify normalized thread events can be accepted through configured parent channel."""
    gateway = DiscordGateway(
        settings=settings(discord_gateway_channel_ids=["parent-channel"]),
        handler=CapturingHandler(),
    )
    event = DiscordMessageEvent(
        message_id="msg-1",
        channel_id="thread-channel",
        channel_name="thread",
        parent_channel_id="parent-channel",
        guild_id="guild-1",
        guild_name="guild",
        author_id="user-1",
        author_name="user",
        content="thread message",
        is_direct_message=False,
        mentions_bot=False,
    )

    assert gateway._should_emit(event) is True


async def test_discord_gateway_filters_author_and_bot_messages() -> None:
    """Verify author allow-list and bot messages are filtered."""
    handler = CapturingHandler()
    gateway = DiscordGateway(
        settings=settings(discord_gateway_user_ids=["allowed-user"]),
        handler=handler,
    )

    await gateway._handle_raw_message(
        make_message(author=make_user("other-user"), content="blocked"),
        bot_user=bot_user(),
    )
    await gateway._handle_raw_message(
        make_message(author=make_user("bot-user", bot=True), content="self"),
        bot_user=bot_user(),
    )
    await gateway._handle_raw_message(
        make_message(author=make_user("allowed-user"), content="allowed"),
        bot_user=bot_user(),
    )

    assert [event.content for event in handler.events] == ["allowed"]
