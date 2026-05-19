from __future__ import annotations

import asyncio
import uuid

from celery.exceptions import Terminated, WorkerShutdown, WorkerTerminate

from src.logger import logger
from src.server.celery.app import celery_app
from src.server.celery.execution import execute_agent_task


_WORKER_INTERRUPTED_EXCEPTIONS = (
    KeyboardInterrupt,
    Terminated,
    WorkerShutdown,
    WorkerTerminate,
)


@celery_app.task(name="nexus.execute_agent_task")
def run_agent_task(
    task_id: str,
    recovered: bool = False,
    dispatch_token: str | None = None,
) -> None:
    try:
        asyncio.run(
            execute_agent_task(
                task_id=uuid.UUID(task_id),
                recovered=recovered,
                dispatch_token=dispatch_token,
            )
        )
    except _WORKER_INTERRUPTED_EXCEPTIONS:
        logger.warning(
            "Celery worker execution for task_id=%s was interrupted by shutdown/termination; skipping failure marking.",
            task_id,
        )
        return
    except Exception as exc:
        logger.exception(
            "Celery worker failed to execute task_id=%s: %s",
            task_id,
            str(exc),
        )
        raise
