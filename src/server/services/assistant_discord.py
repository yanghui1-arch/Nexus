from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import cast

from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from src.agents import Assistant
from src.agents.base.agent import WorkTempStatus
from src.channels.discord import DiscordMessageEvent, DiscordMessageHandler
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, WorkspaceRecord
from src.server.postgres.repositories import AssistantStateRepository, WorkspaceRepository
from src.tools.nexus import NexusAssistantEventContext


@dataclass(frozen=True)
class AssistantDiscordContext:
    """Resolved Assistant workspace context for a Discord chat turn."""

    workspace: WorkspaceRecord
    checkpoint_key: str
    checkpoint: list[ChatCompletionMessageParam]


class AssistantDiscordMessageHandler(DiscordMessageHandler):
    """Handle realtime Discord chat by running Assistant directly.

    Discord chat is interactive transport, not a Celery task. Long-running work
    can still be delegated by Assistant through tools later, but the chat turn
    itself loads a Discord conversation checkpoint, runs one Assistant turn, and
    writes the updated checkpoint back to assistant state.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
    ) -> None:
        self._settings = settings
        self._database = database

    async def handle_message(self, event: DiscordMessageEvent) -> None:
        content = event.content.strip()
        if not content:
            return

        context = await self._load_context(event)
        agent = Assistant.create(
            base_url=self._settings.base_url,
            api_key=self._settings.api_key,
            model=self._settings.model,
            max_context=self._settings.max_context,
            max_attempts=self._settings.max_attempts,
            github_repo=context.workspace.github_repo,
            github_token=self._settings.github_tokens.get(AgentName.assistant.value),
            discord_bot_token=self._settings.discord_gateway_bot_token,
            review_test_commands=self._settings.assistant_test_commands,
            sandbox_workspace_key=context.workspace.workspace_key,
        )
        agent.set_nexus_assistant_event_context(
            NexusAssistantEventContext(
                agent_instance_id=context.workspace.agent_instance_id,
                database=self._database,
                repo=context.workspace.github_repo,
                project=context.workspace.project,
            )
        )

        pending_checkpoint_tasks: set[asyncio.Task[None]] = set()

        def save_checkpoint(status: WorkTempStatus) -> None:
            if status["process"] != "SAVE_CHECKPOINT":
                return
            messages = status.get("context")
            if messages is None:
                return
            checkpoint = _checkpoint_payload(messages)
            task = asyncio.create_task(self._save_checkpoint(context.checkpoint_key, checkpoint))
            pending_checkpoint_tasks.add(task)
            task.add_done_callback(pending_checkpoint_tasks.discard)

        try:
            async with agent:
                await agent.work(
                    question=_build_discord_prompt(event),
                    from_checkpoint=bool(context.checkpoint),
                    checkpoint=context.checkpoint if context.checkpoint else None,
                    update_process_callback=save_checkpoint,
                )
        finally:
            if pending_checkpoint_tasks:
                await asyncio.gather(*pending_checkpoint_tasks)

    async def _load_context(self, event: DiscordMessageEvent) -> AssistantDiscordContext:
        async with self._database.session() as session:
            workspaces = await WorkspaceRepository.list_active_for_agent(
                session,
                agent=AgentName.assistant,
                limit=1,
            )
        if not workspaces:
            raise RuntimeError("No active Assistant workspace is configured for Discord messages.")

        workspace = workspaces[0]
        if not workspace.github_repo or not workspace.project:
            raise RuntimeError("Assistant Discord workspace requires repo and project context.")

        checkpoint_key = _checkpoint_key(event)
        checkpoint = await self._load_checkpoint(checkpoint_key)
        return AssistantDiscordContext(
            workspace=workspace,
            checkpoint_key=checkpoint_key,
            checkpoint=checkpoint,
        )

    async def _load_checkpoint(self, checkpoint_key: str) -> list[ChatCompletionMessageParam]:
        async with self._database.session() as session:
            raw_checkpoint = await AssistantStateRepository.get(session, checkpoint_key)
        if raw_checkpoint is None:
            return []
        payload = json.loads(raw_checkpoint)
        if not isinstance(payload, list):
            raise RuntimeError(f"Assistant Discord checkpoint {checkpoint_key} is not a message list.")
        return cast(list[ChatCompletionMessageParam], payload)

    async def _save_checkpoint(
        self,
        checkpoint_key: str,
        checkpoint: list[ChatCompletionMessageParam],
    ) -> None:
        async with self._database.session() as session:
            await AssistantStateRepository.set(
                session,
                key=checkpoint_key,
                value=json.dumps(checkpoint, ensure_ascii=False),
            )


def _checkpoint_key(event: DiscordMessageEvent) -> str:
    if event.is_direct_message:
        return f"assistant:discord:checkpoint:dm:{event.author_id}"
    guild_id = event.guild_id or "unknown-guild"
    return f"assistant:discord:checkpoint:guild:{guild_id}:channel:{event.channel_id}"


def _build_discord_prompt(event: DiscordMessageEvent) -> str:
    source = "direct message" if event.is_direct_message else "server channel message"
    if event.is_direct_message:
        reply_instruction = (
            "Reply to this Discord direct message by calling `send_discord_dm` "
            f"with user_id `{event.author_id}` before your final answer."
        )
    else:
        reply_instruction = (
            "Reply to this Discord channel message by calling `reply_to_discord_channel_message` "
            f"with channel_id `{event.channel_id}` and message_id `{event.message_id}` before your final answer."
        )
    lines = [
        f"Discord {source} received.",
        f"Author: {event.author_name or event.author_id} ({event.author_id})",
        f"Message ID: {event.message_id}",
        f"Channel ID: {event.channel_id}",
    ]
    if event.guild_id:
        lines.append(f"Guild: {event.guild_name or event.guild_id} ({event.guild_id})")
    if event.channel_name:
        lines.append(f"Channel name: {event.channel_name}")
    lines.extend(
        [
            "",
            "User message:",
            event.content.strip(),
            "",
            reply_instruction,
        ]
    )
    return "\n".join(lines)


def _checkpoint_payload(
    messages: list[ChatCompletionMessageParam | ChatCompletionMessage],
) -> list[ChatCompletionMessageParam]:
    checkpoint: list[ChatCompletionMessageParam] = []
    for message in messages:
        if isinstance(message, dict):
            checkpoint.append(message)
        else:
            checkpoint.append(
                cast(
                    ChatCompletionMessageParam,
                    message.model_dump(mode="json", exclude_none=True),
                )
            )
    return checkpoint
