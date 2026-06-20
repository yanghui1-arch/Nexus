from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.agents.base.agent import BaseAgentResponse
from src.channels.discord import DiscordMessageEvent
from src.server.config import Settings
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AssistantStateRepository, WorkspaceRepository
from src.server.services import assistant_discord
from src.server.services.assistant_discord import AssistantDiscordMessageHandler


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio tests on asyncio only."""
    return "asyncio"


class FakeDatabase:
    def session(self):
        return self

    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *args):
        return None


class FakeAssistant:
    created_kwargs: dict[str, object] = {}
    event_context = None
    work_kwargs: dict[str, object] = {}

    @classmethod
    def create(cls, **kwargs):
        cls.created_kwargs = kwargs
        cls.event_context = None
        return cls()

    def set_nexus_assistant_event_context(self, context):
        self.__class__.event_context = context

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def work(
        self,
        *,
        question,
        from_checkpoint,
        checkpoint,
        update_process_callback,
    ):
        self.__class__.work_kwargs = {
            "question": question,
            "from_checkpoint": from_checkpoint,
            "checkpoint": checkpoint,
        }
        update_process_callback(
            {
                "process": "SAVE_CHECKPOINT",
                "agent_content": "assistant reply",
                "current_use_tool": None,
                "current_use_tool_args": None,
                "context": [
                    {"role": "system", "content": "system"},
                    {"role": "assistant", "content": "assistant reply"},
                ],
            }
        )
        return BaseAgentResponse(response="assistant reply")


def make_settings() -> Settings:
    """Build Settings for Assistant Discord handler tests."""
    return Settings(
        api_key="api-key",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        max_context=4096,
        max_attempts=8,
        github_tokens={"assistant": "assistant-token"},
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
        discord_gateway_channel_ids=[],
        discord_gateway_user_ids=[],
        product_discovery_poll_interval_seconds=3600,
        product_discovery_poll_task_limit=100,
        product_discovery_recent_proposal_limit=5,
        product_discovery_pending_proposal_limit=50,
        product_workflow_poll_interval_seconds=60,
        assistant_enabled=True,
        assistant_github_token="assistant-token",
        assistant_poll_interval_seconds=120,
        assistant_merge_method="squash",
        assistant_test_commands={"owner/repo": ["pytest"]},
    )


def make_event(*, is_direct_message: bool = True) -> DiscordMessageEvent:
    """Build a normalized Discord message event."""
    return DiscordMessageEvent(
        message_id="message-1",
        channel_id="channel-1",
        channel_name="general",
        parent_channel_id=None,
        guild_id=None if is_direct_message else "guild-1",
        guild_name=None if is_direct_message else "Guild",
        author_id="user-1",
        author_name="User",
        content="what changed today?",
        is_direct_message=is_direct_message,
        mentions_bot=False,
    )


async def test_assistant_discord_handler_loads_checkpoint_and_prompts_dm_reply(monkeypatch) -> None:
    """Verify Discord chat resumes checkpoint and asks Assistant to DM through tools."""
    checkpoint = [{"role": "system", "content": "previous"}]
    saved: dict[str, str | None] = {}
    workspace = SimpleNamespace(
        agent_instance_id="assistant-agent-instance-id",
        github_repo="owner/repo",
        project="nexus",
        workspace_key="workspace-key",
    )

    async def fake_list_active_for_agent(session, *, agent, limit):
        assert agent == AgentName.assistant
        assert limit == 1
        return [workspace]

    async def fake_get(session, key):
        assert key == "assistant:discord:checkpoint:dm:user-1"
        return json.dumps(checkpoint)

    async def fake_set(session, *, key, value):
        saved[key] = value
        return SimpleNamespace(key=key, value=value)

    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_list_active_for_agent)
    monkeypatch.setattr(AssistantStateRepository, "get", fake_get)
    monkeypatch.setattr(AssistantStateRepository, "set", fake_set)
    monkeypatch.setattr(assistant_discord.Assistant, "create", FakeAssistant.create)

    handler = AssistantDiscordMessageHandler(settings=make_settings(), database=FakeDatabase())
    await handler.handle_message(make_event())

    assert FakeAssistant.created_kwargs["github_repo"] == "owner/repo"
    assert FakeAssistant.event_context.agent_instance_id == "assistant-agent-instance-id"
    assert FakeAssistant.created_kwargs["sandbox_workspace_key"] == "workspace-key"
    assert FakeAssistant.created_kwargs["discord_bot_token"] == "discord-token"
    assert FakeAssistant.work_kwargs["from_checkpoint"] is True
    assert FakeAssistant.work_kwargs["checkpoint"] == checkpoint
    assert "send_discord_dm" in str(FakeAssistant.work_kwargs["question"])
    assert "user_id `user-1`" in str(FakeAssistant.work_kwargs["question"])

    saved_checkpoint = json.loads(saved["assistant:discord:checkpoint:dm:user-1"] or "[]")
    assert saved_checkpoint[-1] == {"role": "assistant", "content": "assistant reply"}


async def test_assistant_discord_handler_prompts_channel_reply(monkeypatch) -> None:
    """Verify guild messages ask Assistant to reply through tools."""
    workspace = SimpleNamespace(
        agent_instance_id="assistant-agent-instance-id",
        github_repo="owner/repo",
        project="nexus",
        workspace_key="workspace-key",
    )

    async def fake_list_active_for_agent(session, *, agent, limit):
        return [workspace]

    async def fake_get(session, key):
        return None

    async def fake_set(session, *, key, value):
        return SimpleNamespace(key=key, value=value)

    monkeypatch.setattr(WorkspaceRepository, "list_active_for_agent", fake_list_active_for_agent)
    monkeypatch.setattr(AssistantStateRepository, "get", fake_get)
    monkeypatch.setattr(AssistantStateRepository, "set", fake_set)
    monkeypatch.setattr(assistant_discord.Assistant, "create", FakeAssistant.create)

    handler = AssistantDiscordMessageHandler(settings=make_settings(), database=FakeDatabase())
    await handler.handle_message(make_event(is_direct_message=False))

    assert FakeAssistant.work_kwargs["from_checkpoint"] is False
    assert "reply_to_discord_channel_message" in str(FakeAssistant.work_kwargs["question"])
    assert "channel_id `channel-1`" in str(FakeAssistant.work_kwargs["question"])
    assert "message_id `message-1`" in str(FakeAssistant.work_kwargs["question"])
