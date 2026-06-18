from __future__ import annotations

import re
from dataclasses import dataclass

from src.extensions.discord import DiscordMessage, DiscordRestClient
from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.repositories import (
    SecretaryStateRepository,
)

from .service import ReviewTaskDispatchResult, SecretaryService


_COMMAND_CURSOR_KEY = "discord:last_command_id"
_PR_URL_RE = re.compile(r"github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)")
_PR_SHORT_RE = re.compile(r"(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(?P<number>\d+)")


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    repo: str | None = None
    pull_number: int | None = None


class SecretaryCommandProcessor:
    """Polls Discord DMs and dispatches secretary commands."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        service: SecretaryService,
        discord_client: DiscordRestClient | None = None,
    ) -> None:
        """Initialize the command processor."""
        self._settings = settings
        self._database = database
        self._service = service
        discord_token = getattr(settings, "secretary_discord_bot_token", None)
        self._discord = discord_client or (
            DiscordRestClient(discord_token)
            if discord_token
            else None
        )
        self._channel_id: str | None = None

    @property
    def enabled(self) -> bool:
        """Return whether Discord command polling can run."""
        return bool(
            getattr(self._settings, "secretary_enabled", False)
            and getattr(self._settings, "secretary_discord_bot_token", None)
            and getattr(self._settings, "secretary_discord_user_id", None)
            and self._discord is not None
        )

    async def poll_once(self) -> int:
        """Fetch and process new Discord DM commands."""
        if not self.enabled or self._discord is None:
            return 0
        channel_id = await self._ensure_channel_id()
        async with self._database.session() as session:
            cursor = await SecretaryStateRepository.get(session, _COMMAND_CURSOR_KEY)
        messages = await self._discord.fetch_messages(channel_id, after=cursor, limit=50)
        messages = sorted(messages, key=lambda message: _snowflake_sort_key(message.id))

        processed = 0
        for message in messages:
            try:
                if message.author_id != getattr(self._settings, "secretary_discord_user_id", None):
                    continue
                response = await self._handle_message(message)
                if response:
                    await self._discord.send_message(channel_id, response)
                processed += 1
            except Exception as exc:
                logger.exception("Failed to process secretary Discord command %s: %s", message.id, str(exc))
                await self._discord.send_message(
                    channel_id,
                    f"Secretary command failed: {str(exc)}",
                )
            finally:
                async with self._database.session() as session:
                    await SecretaryStateRepository.set(
                        session,
                        key=_COMMAND_CURSOR_KEY,
                        value=message.id,
                    )
        return processed

    async def _handle_message(self, message: DiscordMessage) -> str:
        """Handle one Discord command message."""
        command = parse_command(message.content)
        if command.name == "help":
            return _help_text()
        if command.name == "scan":
            count = await self._service.scan_all()
            return f"Scan finished. Queued {count} review task(s)."
        if command.name == "review":
            if not command.repo or command.pull_number is None:
                return "Usage: `review owner/repo#123` or `review https://github.com/owner/repo/pull/123`"
            result = await self._service.review_one(command.repo, command.pull_number, force=True)
            return _format_review_result(result)
        if command.name == "status":
            if not command.repo or command.pull_number is None:
                return "Usage: `status owner/repo#123`"
            return await self._status(command.repo, command.pull_number)
        return _help_text()

    async def _status(self, repo: str, pull_number: int) -> str:
        """Return the latest secretary status for one PR."""
        task = await self._service.latest_status(repo, pull_number)
        if task is None:
            return f"No Assistant review task recorded for {repo}#{pull_number}."
        return (
            f"{repo}#{pull_number} Assistant review task\n"
            f"task: `{task.id}`\n"
            f"status: `{task.status.value}`\n"
            f"result: {task.result or task.error or 'not finished'}\n"
            f"{task.external_pull_request_url or ''}"
        )

    async def _ensure_channel_id(self) -> str:
        """Create or reuse the configured DM channel."""
        if self._channel_id is not None:
            return self._channel_id
        if self._discord is None or not getattr(self._settings, "secretary_discord_user_id", None):
            raise RuntimeError("Discord command processor is not configured.")
        self._channel_id = await self._discord.create_dm(
            getattr(self._settings, "secretary_discord_user_id")
        )
        return self._channel_id


def parse_command(content: str) -> ParsedCommand:
    """Parse a Discord DM command."""
    text = (content or "").strip()
    if not text:
        return ParsedCommand("help")
    if text.startswith("/"):
        text = text[1:]
    lowered = text.casefold()
    if lowered.startswith("secretary "):
        text = text.split(" ", 1)[1].strip()
        lowered = text.casefold()

    if lowered in {"help", "?", "commands"}:
        return ParsedCommand("help")
    if lowered == "scan":
        return ParsedCommand("scan")
    for name in ("review", "status"):
        if lowered == name:
            return ParsedCommand(name)
        if lowered.startswith(f"{name} "):
            repo, number = _parse_pr_target(text.split(" ", 1)[1].strip())
            return ParsedCommand(name, repo=repo, pull_number=number)
    return ParsedCommand("help")


def _parse_pr_target(value: str) -> tuple[str | None, int | None]:
    """Parse a PR URL or owner/repo#number target."""
    match = _PR_URL_RE.search(value)
    if match is None:
        match = _PR_SHORT_RE.search(value)
    if match is None:
        return None, None
    return match.group("repo"), int(match.group("number"))


def _format_review_result(result: ReviewTaskDispatchResult) -> str:
    """Build a command response from a review task dispatch."""
    return (
        f"{result.message} {result.repo}#{result.pull_number}\n"
        f"task: `{result.task_id}`\n"
        f"{result.pull_request_url}"
    )


def _help_text() -> str:
    """Return command help text."""
    return (
        "Secretary commands:\n"
        "`scan` - scan configured repositories now\n"
        "`review owner/repo#123` - force review one PR\n"
        "`review https://github.com/owner/repo/pull/123` - force review one PR\n"
        "`status owner/repo#123` - show latest secretary status"
    )


def _snowflake_sort_key(value: str) -> int:
    """Sort Discord snowflake ids numerically when possible."""
    try:
        return int(value)
    except ValueError:
        return 0
