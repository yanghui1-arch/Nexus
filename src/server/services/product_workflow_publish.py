from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.postgres.models import AgentName, FeatureItemRecord, ProductProposalRecord
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository, TaskRepository
from src.server.runner import AgentTaskRunner
from src.server.schemas import AgentKind, TaskCreateRequest


class NoActiveTelaAgentInstanceError(RuntimeError):
    """Raised when no Tela instance can run a feature item."""


async def publish_feature_item_task(
    session: AsyncSession,
    *,
    runner: AgentTaskRunner,
    item: FeatureItemRecord,
    proposal: ProductProposalRecord,
    require_unassigned: bool,
) -> tuple[FeatureItemRecord | None, uuid.UUID, uuid.UUID]:
    """Publish a coding task and attach it to a feature item.

    ``require_unassigned`` is intentionally caller-controlled: background
    publishing should only claim unassigned pending items, while retry must
    replace the failed task id already stored on the item.
    """
    tela_instances = await AgentInstanceRepository.list_by_active_task_load(
        session,
        agent=AgentName.tela,
        user_id=proposal.user_id,
        github_repo=proposal.repo,
        project=proposal.project,
        limit=1,
    )
    if not tela_instances:
        raise NoActiveTelaAgentInstanceError
    agent_instance_id = tela_instances[0].id
    task_id = await runner.submit_task(
        TaskCreateRequest(
            agent_instance_id=agent_instance_id,
            agent=AgentKind.tela,
            question=build_feature_item_coding_question(item),
            external_issue_url=None,
        )
    )
    assigned = await FeatureItemRepository.assign_task(
        session, item.id, task_id=task_id, require_unassigned=require_unassigned
    )
    if assigned is None:
        await TaskRepository.set_closed(session, task_id)
        logger.warning("Feature item %s was already assigned before publishing task %s.", item.id, task_id)
    return assigned, task_id, agent_instance_id


def build_feature_item_coding_question(item: Any) -> str:
    return f"Implement product feature item: {item.title}\n\n{item.description}"
