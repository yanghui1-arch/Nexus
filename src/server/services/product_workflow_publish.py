from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.server.postgres.models import AgentName, FeatureItemRecord, ProductProposalRecord
from src.server.postgres.repositories import AgentInstanceRepository, FeatureItemRepository
from src.server.runner import AgentTaskRunner, TaskSubmission


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
    # Bind the feature item before dispatch so worker failures can always resolve
    # the feature item by task_id and sync it to failed.
    task = await runner.create_task_record(
        TaskSubmission(
            agent_instance_id=agent_instance_id,
            agent=AgentName.tela,
            question=build_feature_item_coding_question(item),
            external_issue_url=None,
        ),
        session=session,
    )
    assigned = await FeatureItemRepository.assign_task(
        session, item.id, task_id=task.id, require_unassigned=require_unassigned
    )
    if assigned is None:
        logger.warning("Feature item %s was already assigned before publishing task %s.", item.id, task.id)
        return assigned, task.id, agent_instance_id
    await runner.dispatch_task(task.id)
    return assigned, task.id, agent_instance_id


def build_feature_item_coding_question(item: Any) -> str:
    return f"Implement product feature item: {item.title}\n\n{item.description}"
