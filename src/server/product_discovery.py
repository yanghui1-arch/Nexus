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
RECENT_PROPOSAL_PROMPT_LIMIT = 5


def build_product_discovery_prompt(
    *,
    project: str,
    repo: str | None,
    pending_proposal_count: int,
    recent_proposals: list[Any],
) -> str:
    """Build the product discovery task prompt."""
    repo_context = repo or "未配置"
    recent_lines = []
    for proposal in recent_proposals[:RECENT_PROPOSAL_PROMPT_LIMIT]:
        status = getattr(proposal, "status", "unknown")
        status_value = getattr(status, "value", str(status))
        recent_lines.append(f"- {proposal.title} ({status_value})")
    recent_summary = "\n".join(recent_lines) if recent_lines else "- 暂无近期 proposal"

    return (
        "优化产品并提出一个proposal\n\n"
        "中文产品发现任务目标：结合当前项目上下文、代码库事实和用户价值，发现一个高价值产品改进机会，"
        "并创建清晰、可评审的 proposal。\n"
        f"项目上下文：project={project}; repo={repo_context}\n"
        f"待处理 proposal 数量：{pending_proposal_count}\n"
        "近期 proposal（标题/状态）：\n"
        f"{recent_summary}\n"
        "避免重复：不要创建与近期 proposal 标题、目标或范围重复的 proposal；"
        "如主题相近，请明确差异化价值和边界。"
    )


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

                async with self._database.session() as session:
                    recent_proposals = await ProductProposalRepository.list(
                        session,
                        project=workspace.project,
                        repo=workspace.github_repo,
                        limit=RECENT_PROPOSAL_PROMPT_LIMIT,
                    )
                    pending_proposals = await ProductProposalRepository.list(
                        session,
                        status=ProductProposalStatus.proposed,
                        project=workspace.project,
                        repo=workspace.github_repo,
                        limit=200,
                    )

                task_id = await self._runner.submit_task(
                    TaskCreateRequest(
                        agent_instance_id=instance.id,
                        agent=AgentKind(instance.agent.value),
                        question=build_product_discovery_prompt(
                            project=workspace.project,
                            repo=workspace.github_repo,
                            pending_proposal_count=len(pending_proposals),
                            recent_proposals=recent_proposals,
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
