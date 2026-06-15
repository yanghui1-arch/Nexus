from __future__ import annotations

import asyncio
from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.repositories import FeatureItemRepository
from src.server.runner import AgentTaskRunner
from src.server.services import product_workflow_dispatch
from src.server.services.product_workflow_publish import (
    NoActiveTelaAgentInstanceError,
    publish_feature_item_task,
)


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
        if self._settings.product_workflow_poll_interval_seconds <= 0:
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
            round_published = await self._publish_one_dispatch_round()
            if round_published == 0:
                return published_count
            published_count += round_published
        return published_count

    async def _publish_one_dispatch_round(self) -> int:
        """Publish at most one item per `(user, repo, project)` group."""
        async with self._database.session() as session:
            dispatch_groups = await product_workflow_dispatch.list_pending_dispatch_groups(session)
        published_count = 0
        for dispatch_group in dispatch_groups:
            if self._stop_event.is_set():
                break
            # Round-robin across workflow groups so one user's unavailable Tela
            # does not block other users' pending feature items.
            published = await self._publish_one_feature_item_for_group(dispatch_group)
            if published:
                published_count += 1
        return published_count

    async def _publish_one_feature_item_for_group(
        self,
        dispatch_group: product_workflow_dispatch.FeatureItemDispatchGroup,
    ) -> bool:
        """Publish the next pending feature item for one workflow group."""
        async with self._database.session() as session:
            item = await product_workflow_dispatch.get_next_unassigned_for_dispatch_group(
                session,
                dispatch_group=dispatch_group,
            )
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
            try:
                assigned, task_id, _ = await publish_feature_item_task(
                    session,
                    runner=self._runner,
                    item=item,
                    proposal=proposal,
                    # Polling claims only still-unassigned pending items so a
                    # concurrent publisher cannot overwrite an existing task.
                    require_unassigned=True,
                )
            except NoActiveTelaAgentInstanceError:
                logger.warning(
                    "Skip feature item %s because no active Tela agent instance is available for user=%s repo=%s project=%s.",
                    item.id,
                    proposal.user_id,
                    proposal.repo,
                    proposal.project,
                )
                return False
        if assigned is None:
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
                    timeout=self._settings.product_workflow_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue
