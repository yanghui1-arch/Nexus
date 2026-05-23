from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import (
    AgentInstanceRecord,
    AgentName,
    ProductProposalRecord,
    ProductProposalStatus,
    TaskCategory,
    WorkspaceRecord,
)
from src.server.postgres.repositories import (
    AgentInstanceRepository,
    ProductProposalRepository,
    TaskRepository,
    WorkspaceRepository,
)
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


PRODUCT_DISCOVERY_AGENT_NAMES = {AgentName.marc}
PENDING_PROPOSAL_LIMIT = 3

ProductDiscoveryAction = Literal["dispatch", "skip"]


@dataclass(frozen=True)
class ProductDiscoveryDecisionReason:
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductDiscoveryDecision:
    action: ProductDiscoveryAction
    reason: ProductDiscoveryDecisionReason


@dataclass(frozen=True)
class ProductDiscoveryProposalMetrics:
    pending_proposal_count: int
    pending_proposal_limit: int
    cooldown_seconds: int
    latest_discovery_or_proposal_at: datetime | None = None


def _skip(code: str, message: str, **details: object) -> ProductDiscoveryDecision:
    return ProductDiscoveryDecision("skip", ProductDiscoveryDecisionReason(code, message, details))


def decide_product_discovery_dispatch(
    *,
    candidate: AgentInstanceRecord,
    workspace: WorkspaceRecord | None,
    metrics: ProductDiscoveryProposalMetrics,
    now: datetime | None = None,
) -> ProductDiscoveryDecision:
    """Decide whether a product discovery candidate should be dispatched."""
    candidate_id = getattr(candidate, "id", None)
    if workspace is None:
        return _skip("missing_workspace", "Workspace context is missing.", candidate_id=candidate_id)

    repo = getattr(workspace, "github_repo", None)
    project = getattr(workspace, "project", None)
    if not repo or not project:
        return _skip(
            "missing_workspace_context",
            "Workspace repository or project context is missing.",
            candidate_id=candidate_id,
            repo=repo,
            project=project,
        )

    if metrics.pending_proposal_count >= metrics.pending_proposal_limit:
        return _skip(
            "pending_proposal_limit_reached",
            "Pending product proposal limit has been reached.",
            pending_proposal_count=metrics.pending_proposal_count,
            pending_proposal_limit=metrics.pending_proposal_limit,
            repo=repo,
            project=project,
        )

    if metrics.latest_discovery_or_proposal_at is not None and metrics.cooldown_seconds > 0:
        current_time = now or datetime.now(UTC)
        cooldown_until = metrics.latest_discovery_or_proposal_at + timedelta(seconds=metrics.cooldown_seconds)
        if current_time < cooldown_until:
            return _skip(
                "cooldown_active",
                "Recent product discovery or proposal is still within cooldown.",
                latest_discovery_or_proposal_at=metrics.latest_discovery_or_proposal_at.isoformat(),
                cooldown_until=cooldown_until.isoformat(),
                repo=repo,
                project=project,
            )

    return ProductDiscoveryDecision(
        action="dispatch",
        reason=ProductDiscoveryDecisionReason(
            "dispatch_allowed",
            "Product discovery dispatch is allowed.",
            {"candidate_id": str(candidate_id), "repo": repo, "project": project},
        ),
    )


def build_product_discovery_question(proposals: list[ProductProposalRecord], *, proposal_limit: int) -> str:
    """Build a bounded product discovery prompt from recent proposals."""
    lines = [
        "优化产品并提出一个proposal",
        "",
        "Recent proposals context (title and summary only):",
    ]
    for proposal in proposals[:proposal_limit]:
        title = (proposal.title or "").strip()
        summary = (proposal.summary or "").strip()
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
                    workspace = await WorkspaceRepository.get_by_agent_instance_id(session, instance.id)
                    metrics = await self._proposal_metrics(session, workspace)

                decision = decide_product_discovery_dispatch(
                    candidate=instance,
                    workspace=workspace,
                    metrics=metrics,
                )
                if decision.action == "skip":
                    logger.info(
                        "Skip product discovery for agent instance %s: %s",
                        instance.id,
                        decision.reason,
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

    async def _proposal_metrics(
        self,
        session: AsyncSession,
        workspace: WorkspaceRecord | None,
    ) -> ProductDiscoveryProposalMetrics:
        """Build proposal metrics for a workspace."""
        interval = self._settings.product_discovery_poll_interval_seconds
        if workspace is None or not getattr(workspace, "github_repo", None) or not getattr(workspace, "project", None):
            return ProductDiscoveryProposalMetrics(0, PENDING_PROPOSAL_LIMIT, interval)

        proposals = await ProductProposalRepository.list(session, repo=workspace.github_repo, project=workspace.project)
        pending_count = sum(
            proposal.status in {ProductProposalStatus.proposed, ProductProposalStatus.approved, ProductProposalStatus.planned}
            for proposal in proposals
        )
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
        return ProductDiscoveryProposalMetrics(pending_count, PENDING_PROPOSAL_LIMIT, interval, latest_at)

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
