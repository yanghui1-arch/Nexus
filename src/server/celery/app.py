from __future__ import annotations

from celery import Celery

from src.server.config import get_settings


settings = get_settings()
broker_timeout = settings.celery_broker_connection_timeout_seconds

celery_app = Celery(
    "nexus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue=settings.celery_queue,
    # Agentic coding has non-idempotent side effects (git push, PR comments, etc.).
    # Ack early to avoid duplicate re-execution after worker loss.
    task_acks_late=False,
    # Keep lost-worker tasks from being force-requeued by broker semantics.
    task_reject_on_worker_lost=False,
    # Explicitly keep default failure/timeout ack behavior.
    task_acks_on_failure_or_timeout=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=broker_timeout,
    broker_transport_options={
        "visibility_timeout": settings.celery_visibility_timeout_seconds,
        # Redis transport forwards these to redis-py; keep them aligned with
        # the broker timeout so send_task() cannot block indefinitely during
        # broker outages.
        "socket_connect_timeout": broker_timeout,
        "socket_timeout": broker_timeout,
    },
    # Redis-specific Celery aliases cover both broker/backend Redis clients.
    redis_socket_connect_timeout=broker_timeout,
    redis_socket_timeout=broker_timeout,
    # Apply a bounded retry policy to every Celery publish, including send_task().
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": settings.celery_task_publish_max_retries,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.2,
    },
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
)

celery_app.autodiscover_tasks(["src.server.celery"])
