from __future__ import annotations

import asyncio
import uuid

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.celery.execution import AgentTaskLeaseDeferred, execute_agent_task


@celery_app.task(bind=True, name="nexus.execute_agent_task", max_retries=None)
def run_agent_task(
    self,
    task_id: str,
    recovered: bool = False,
    dispatch_token: str | None = None,
) -> None:
    """Run an agent task from Celery."""
    try:
        asyncio.run(
            execute_agent_task(
                task_id=uuid.UUID(task_id),
                recovered=recovered,
                dispatch_token=dispatch_token,
            )
        )
    except AgentTaskLeaseDeferred as exc:
        raise self.retry(exc=exc, countdown=exc.countdown_seconds)
    except Exception as exc:
        logger.exception(
            "Celery worker failed to execute task_id=%s: %s",
            task_id,
            str(exc),
        )
        raise
