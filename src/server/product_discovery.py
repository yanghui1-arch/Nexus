from __future__ import annotations

import asyncio

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, ProductProposalRecord
from src.server.postgres.repositories import AgentInstanceRepository, ProductProposalRepository, WorkspaceRepository
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


PRODUCT_DISCOVERY_AGENT_NAMES = {AgentName.marc}
MAX_PROPOSAL_TITLE_CHARS = 120
MAX_PROPOSAL_SUMMARY_CHARS = 500


def build_product_discovery_question(proposals: list[ProductProposalRecord], *, proposal_limit: int) -> str:
    """Build a bounded product discovery prompt from recent proposals."""
    lines = [
        "优化产品并提出一个proposal",
        "",
        "Recent proposals context (title and summary only):",
    ]
    for proposal in proposals[: max(0, proposal_limit)]:
        title = (proposal.title or "").strip()
        summary = (proposal.summary or "").strip()
        if len(title) > MAX_PROPOSAL_TITLE_CHARS:
            title = f"{title[: MAX_PROPOSAL_TITLE_CHARS - 1]}…"
        if len(summary) > MAX_PROPOSAL_SUMMARY_CHARS:
            summary = f"{summary[: MAX_PROPOSAL_SUMMARY_CHARS - 1]}…"
        lines.extend([f"- Title: {title}", f"  Summary: {summary}"])
    if len(lines) == 3:
        lines.append("- None")
    return "\n".join(lines)


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
        self._task: asyncio.Task[None] | None = None

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
                if workspace is None:
                    logger.warning(
                        "Skip product discovery for agent instance %s because workspace is missing.",
                        instance.id,
                    )
                    continue
                if not workspace.project:
                    logger.warning(
                        "Skip product discovery for agent instance %s because workspace project is missing.",
                        instance.id,
                    )
                    continue
                recent_limit = self._settings.product_discovery_recent_proposal_limit
                async with self._database.session() as session:
                    recent_proposals = await ProductProposalRepository.list(
                        session,
                        project=workspace.project,
                        repo=workspace.github_repo,
                        limit=recent_limit,
                    )

                task_id = await self._runner.submit_task(
                    TaskCreateRequest(
                        agent_instance_id=instance.id,
                        agent=AgentKind(instance.agent.value),
                        question=build_product_discovery_question(
                            recent_proposals,
                            proposal_limit=recent_limit,
                        ),
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
