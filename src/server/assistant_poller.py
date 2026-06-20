from __future__ import annotations

import asyncio

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.runner import AgentTaskRunner
from src.server.services.assistant import AssistantService
from src.server.services.background import BackgroundService


class AssistantPoller(BackgroundService):
    """Background poller for scheduled Assistant PR scans."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner | None = None,
        service: AssistantService | None = None,
    ) -> None:
        """Initialize the poller."""
        self._settings = settings
        self._database = database
        self._runner = runner
        self._service = service or AssistantService(
            settings=settings,
            database=database,
            runner=runner,
        )
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start the background assistant poller."""
        if not self._settings.assistant_enabled:
            logger.info("Assistant poller is disabled.")
            return
        if self._settings.assistant_poll_interval_seconds <= 0:
            logger.info("Assistant poller interval is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="nexus-assistant-poller")
        logger.info("Assistant poller starts.")

    async def stop(self) -> None:
        """Stop the background assistant poller."""
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def poll_once(self) -> int:
        """Run one scheduled Assistant scan cycle."""
        return await self._service.scan_all()

    async def _run_loop(self) -> None:
        """Run the background loop."""
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Assistant poller iteration failed.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._settings.assistant_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue
