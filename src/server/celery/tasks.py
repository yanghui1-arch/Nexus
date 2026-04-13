from __future__ import annotations

import asyncio
import uuid

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.celery.execution import execute_agent_task
from src.server.schemas import TaskCreateRequest


@celery_app.task(name="nexus.execute_agent_task")
def run_agent_task(
    task_id: str,
    request_payload: dict,
    recovered: bool = False,
    dispatch_token: str | None = None,
) -> None:
    try:
        request = TaskCreateRequest.model_validate(request_payload)
        asyncio.run(
            execute_agent_task(
                task_id=uuid.UUID(task_id),
                request=request,
                recovered=recovered,
                dispatch_token=dispatch_token,
            )
        )
    except Exception as exc:
        logger.exception(
            "Celery worker failed to execute task_id=%s: %s",
            task_id,
            str(exc),
        )
        raise
