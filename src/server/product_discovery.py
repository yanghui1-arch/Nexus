from __future__ import annotations

import asyncio
from typing import Any

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AgentInstanceRepository, TaskRepository, WorkspaceRepository
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


PRODUCT_DISCOVERY_AGENT_NAMES = {AgentName.marc}


class ProductDiscoveryPoller:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        runner: AgentTaskRunner,
    ) -> None:
        """Initialize the service component."""
        self._settings = settings
        self._database = database
        self._runner = runner
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None

    def start(self) -> None:
        """Start the product discovery poller.

        The default cadence is intentionally sparse so discovery agents can
        periodically propose product improvements without overloading the team.
        """
        if self._settings.product_discovery_poll_interval_seconds <= 0:
            logger.info("Product discovery poller is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="nexus-product-discovery-poller")
        logger.info("Product discovery poller starts.")

    async def stop(self) -> None:
        """Stop the background poller."""
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def poll_once(self) -> int:
        """Run one polling cycle."""
        async with self._database.session() as session:
            candidates = await AgentInstanceRepository.list_product_discovery_candidates(
                session,
                limit=self._settings.product_discovery_poll_task_limit,
            )

        if len(candidates) >= self._settings.product_discovery_poll_task_limit:
            logger.info(
                "Product discovery candidate list reached pending limit: pending_count=%s limit=%s.",
                len(candidates),
                self._settings.product_discovery_poll_task_limit,
            )

        dispatched_count = 0
        for instance in candidates:
            if self._stop_event.is_set():
                break
            if instance.agent not in PRODUCT_DISCOVERY_AGENT_NAMES:
                continue

            try:
                async with self._database.session() as session:
                    workspace = await WorkspaceRepository.get_by_agent_instance_id(
                        session,
                        instance.id,
                    )
                    pending_count = await TaskRepository.count_active_pm_tasks(
                        session,
                        agent_instance_id=instance.id,
                    )
                if workspace is None:
                    logger.warning(
                        "Skipped product discovery candidate: agent_instance_id=%s workspace_id=%s repo=%s project=%s reason=%s pending_count=%s cooldown_last_used_at=%s cooldown_updated_at=%s cooldown_interval_seconds=%s.",
                        instance.id,
                        None,
                        None,
                        None,
                        "missing_workspace",
                        pending_count,
                        None,
                        None,
                        self._settings.product_discovery_poll_interval_seconds,
                    )
                    continue
                if pending_count > 0:
                    logger.info(
                        "Skipped product discovery candidate: agent_instance_id=%s workspace_id=%s repo=%s project=%s reason=%s pending_count=%s cooldown_last_used_at=%s cooldown_updated_at=%s cooldown_interval_seconds=%s.",
                        instance.id,
                        workspace.id,
                        workspace.github_repo,
                        workspace.project,
                        "cooldown_active_task",
                        pending_count,
                        workspace.last_used_at,
                        workspace.updated_at,
                        self._settings.product_discovery_poll_interval_seconds,
                    )
                    continue
                if not workspace.github_repo or not workspace.project:
                    logger.warning(
                        "Skipped product discovery candidate: agent_instance_id=%s workspace_id=%s repo=%s project=%s reason=%s pending_count=%s cooldown_last_used_at=%s cooldown_updated_at=%s cooldown_interval_seconds=%s.",
                        instance.id,
                        workspace.id,
                        workspace.github_repo,
                        workspace.project,
                        "missing_context",
                        pending_count,
                        workspace.last_used_at,
                        workspace.updated_at,
                        self._settings.product_discovery_poll_interval_seconds,
                    )
                    continue

                task_id = await self._runner.submit_task(
                    TaskCreateRequest(
                        agent_instance_id=instance.id,
                        agent=AgentKind(instance.agent.value),
                        question="优化产品并提出一个proposal",
                        external_issue_url=None,
                    )
                )
            except Exception as exc:
                logger.exception(
                    "Failed to dispatch product discovery for agent instance %s: %s",
                    instance.id,
                    str(exc),
                )
                continue

            dispatched_count += 1
            logger.info(
                "Dispatched product discovery candidate: agent_instance_id=%s workspace_id=%s repo=%s project=%s reason=%s pending_count=%s cooldown_last_used_at=%s cooldown_updated_at=%s cooldown_interval_seconds=%s task_id=%s.",
                instance.id,
                workspace.id,
                workspace.github_repo,
                workspace.project,
                "dispatch",
                pending_count,
                workspace.last_used_at,
                workspace.updated_at,
                self._settings.product_discovery_poll_interval_seconds,
                task_id,
            )

        return dispatched_count

    async def _run_loop(self) -> None:
        """Run the background polling loop."""
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Product discovery poller iteration failed.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._settings.product_discovery_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue
