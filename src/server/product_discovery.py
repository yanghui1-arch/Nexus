from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, TaskCategory
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


PRODUCT_DISCOVERY_AGENT_NAMES = {AgentName.marc}


def _is_in_cooldown(
    latest_activity_at: datetime | None,
    *,
    cooldown_seconds: int,
    now: datetime | None = None,
) -> bool:
    """Return whether recent discovery/proposal activity is still cooling down."""
    if latest_activity_at is None or cooldown_seconds <= 0:
        return False
    return (now or datetime.now(UTC)) < latest_activity_at + timedelta(seconds=cooldown_seconds)


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
                    latest_activity_at = await self._latest_discovery_activity_at(session, workspace)
                if workspace is None:
                    logger.warning(
                        "Skip product discovery for agent instance %s because workspace is missing.",
                        instance.id,
                    )
                    continue
                if not workspace.github_repo or not workspace.project:
                    logger.warning(
                        "Skip product discovery for agent instance %s because workspace repo/project is missing.",
                        instance.id,
                    )
                    continue
                if _is_in_cooldown(
                    latest_activity_at,
                    cooldown_seconds=self._settings.product_discovery_poll_interval_seconds,
                ):
                    logger.info(
                        "Skip product discovery for agent instance %s because repo/project is in cooldown.",
                        instance.id,
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
                "Queued product discovery task %s for agent instance %s.",
                task_id,
                instance.id,
            )

        return dispatched_count

    async def _latest_discovery_activity_at(self, session: Any, workspace: Any | None) -> datetime | None:
        """Return latest product discovery task or proposal time for a workspace."""
        if workspace is None or not getattr(workspace, "github_repo", None) or not getattr(workspace, "project", None):
            return None

        proposals = await ProductProposalRepository.list(session, repo=workspace.github_repo, project=workspace.project)
        latest_at = max((proposal.created_at for proposal in proposals), default=None)
        tasks = await TaskRepository.list(
            session,
            category=TaskCategory.pm,
            repo=workspace.github_repo,
            project=workspace.project,
            limit=1,
        )
        if tasks:
            latest_at = tasks[0].created_at if latest_at is None else max(latest_at, tasks[0].created_at)
        return latest_at

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
