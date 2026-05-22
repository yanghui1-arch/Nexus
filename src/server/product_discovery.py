from __future__ import annotations

import asyncio
from typing import Any

from src.logger import logger
from src.server.config import Settings
from src.server.postgres.database import Database
from src.server.postgres.models import AgentName, ProductProposalStatus
from src.server.postgres.repositories import AgentInstanceRepository, ProductProposalRepository, WorkspaceRepository
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


PRODUCT_DISCOVERY_AGENT_NAMES = {AgentName.marc}
DISCOVERY_PROPOSAL_STATUS_LABELS = {
    ProductProposalStatus.proposed: "pending(proposed)",
    ProductProposalStatus.approved: "approved",
    ProductProposalStatus.rejected: "rejected",
}


def build_product_discovery_prompt(
    *,
    project: str,
    repo: str | None = None,
    proposal_counts: dict[ProductProposalStatus, int] | None = None,
    recent_proposals: list[Any] | None = None,
) -> str:
    """Build a context-aware prompt for periodic product discovery."""
    identity = f"project={project}"
    if repo:
        identity = f"repo={repo}, {identity}"

    lines = [
        "请为当前产品做一次上下文感知的 discovery，并提出一个新的 product proposal。",
        f"目标上下文：{identity}。",
    ]
    if proposal_counts:
        counts = ", ".join(
            f"{label}={proposal_counts.get(status, 0)}" for status, label in DISCOVERY_PROPOSAL_STATUS_LABELS.items()
        )
        lines.append(f"当前 proposal 计数：{counts}。")
    else:
        lines.append("当前 proposal 计数不可用；请基于仓库和项目上下文谨慎判断。")

    if recent_proposals:
        lines.append("最近已有 proposals（title / status / summary）：")
        for proposal in recent_proposals:
            title = getattr(proposal, "title", "Untitled") or "Untitled"
            status = getattr(getattr(proposal, "status", None), "value", getattr(proposal, "status", "unknown"))
            summary = getattr(proposal, "summary", "") or "无摘要"
            lines.append(f"- {title} / {status} / {summary}")
    else:
        lines.append("最近 proposal 信息不可用；请避免提出泛泛而谈或明显重复的建议。")

    lines.append("明确要求：不要重复已有 proposal，优先发现不同且高价值的产品机会。")
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

                recent_proposals = None
                proposal_counts = None
                try:
                    async with self._database.session() as session:
                        proposals = await ProductProposalRepository.list(
                            session,
                            project=workspace.project,
                            repo=workspace.github_repo,
                            limit=200,
                        )
                    proposal_counts = {
                        status: sum(1 for proposal in proposals if proposal.status == status)
                        for status in DISCOVERY_PROPOSAL_STATUS_LABELS
                    }
                    recent_proposals = proposals[:5]
                except Exception as exc:
                    logger.warning(
                        "Build product discovery prompt without proposal metrics for agent instance %s: %s",
                        instance.id,
                        str(exc),
                    )
                question = build_product_discovery_prompt(
                    project=workspace.project,
                    repo=workspace.github_repo,
                    proposal_counts=proposal_counts,
                    recent_proposals=recent_proposals,
                )

                task_id = await self._runner.submit_task(
                    TaskCreateRequest(
                        agent_instance_id=instance.id,
                        agent=AgentKind(instance.agent.value),
                        question=question,
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
