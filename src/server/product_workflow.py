from __future__ import annotations

import asyncio
from typing import Any

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository, TaskRepository
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


class ProductWorkflowPoller:
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
        """Start the background poller."""
        if self._settings.product_discovery_poll_interval_seconds <= 0:
            logger.info("Product workflow poller is disabled.")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="nexus-product-workflow-poller")
        logger.info("Product workflow poller starts.")

    async def stop(self) -> None:
        """Stop the background poller."""
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def poll_once(self) -> int:
        """Run one polling cycle."""
        published_count = 0
        while not self._stop_event.is_set():
            published = await self._publish_one_feature_item()
            if not published:
                return published_count
            published_count += 1
        return published_count

    async def _publish_one_feature_item(self) -> bool:
        """Publish one pending feature item as a coding task."""
        async with self._database.session() as session:
            item = await FeatureItemRepository.get_next_unassigned(session)
            if item is None:
                return False
            if await FeatureItemRepository.get_feature(session, item.id) is None:
                logger.warning("Skip feature item %s because its feature is missing.", item.id)
                return False
            # Feature items inherit ownership from their proposal workspace. Use the
            # proposal repo/project when choosing a Tela instance so product work
            # is not published to an agent that belongs to another workspace.
            proposal = await FeatureItemRepository.get_proposal(session, item.id)
            if proposal is None:
                logger.warning("Skip feature item %s because its proposal is missing.", item.id)
                return False
            tela_instances = await AgentInstanceRepository.list_by_active_task_load(
                session,
                agent=AgentName.tela,
                github_repo=proposal.repo,
                project=proposal.project,
                limit=1,
            )
            if not tela_instances:
                logger.warning("Skip feature item task publishing because no active Tela agent instance is available.")
                return False

        task_id = await self._runner.submit_task(
            TaskCreateRequest(
                agent_instance_id=tela_instances[0].id,
                agent=AgentKind.tela,
                question=_build_feature_item_coding_question(item),
                external_issue_url=None,
            )
        )
        async with self._database.session() as session:
            assigned = await FeatureItemRepository.assign_task(session, item.id, task_id=task_id)
        if assigned is None:
            async with self._database.session() as session:
                await TaskRepository.set_closed(session, task_id)
            logger.warning("Feature item %s was already assigned before publishing task %s.", item.id, task_id)
            return False
        return True

    async def _run_loop(self) -> None:
        """Run the background polling loop."""
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Product workflow poller iteration failed.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._settings.product_discovery_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue


def _build_feature_item_coding_question(item: Any) -> str:
    """Build the coding prompt for a feature item."""
    return f"Implement product feature item: {item.title}\n\n{item.description}"
