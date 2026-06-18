from __future__ import annotations

import asyncio
from typing import Any

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.runner import AgentTaskRunner

from .commands import SecretaryCommandProcessor
from .service import SecretaryService


class SecretaryPoller:
    """Background poller for Discord secretary PR scans and commands."""

    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner | None = None,
        service: SecretaryService | None = None,
        command_processor: SecretaryCommandProcessor | None = None,
    ) -> None:
        """Initialize the poller."""
        self._settings = settings
        self._database = database
        self._runner = runner
        self._service = service or SecretaryService(
            settings=settings,
            database=database,
            runner=runner,
        )
        self._command_processor = command_processor or SecretaryCommandProcessor(
            settings=settings,
            database=database,
            service=self._service,
        )
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None

    def start(self) -> None:
        """Start the background secretary poller."""
        if not getattr(self._settings, "secretary_enabled", False):
            logger.info("Secretary poller is disabled.")
            return
        if getattr(self._settings, "secretary_poll_interval_seconds", 0) <= 0:
            logger.info("Secretary poller interval is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="nexus-secretary-poller")
        logger.info("Secretary poller starts.")

    async def stop(self) -> None:
        """Stop the background secretary poller."""
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def poll_once(self) -> int:
        """Run one secretary scan/command cycle."""
        processed = 0
        processed += await self._command_processor.poll_once()
        processed += await self._service.scan_all()
        return processed

    async def _run_loop(self) -> None:
        """Run the background loop."""
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Secretary poller iteration failed.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=getattr(self._settings, "secretary_poll_interval_seconds", 120),
                )
            except asyncio.TimeoutError:
                continue
