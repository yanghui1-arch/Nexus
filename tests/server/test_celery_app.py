from __future__ import annotations

import importlib

from src.server.config import get_settings


def test_celery_app_bounds_global_publish_retries_and_timeouts(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CELERY_QUEUE", "test-agent-tasks")
    monkeypatch.setenv("NEXUS_CELERY_VISIBILITY_TIMEOUT_SECONDS", "123")
    monkeypatch.setenv("NEXUS_CELERY_TASK_PUBLISH_MAX_RETRIES", "3")
    monkeypatch.setenv("NEXUS_CELERY_BROKER_CONNECTION_TIMEOUT_SECONDS", "2.0")
    get_settings.cache_clear()

    import src.server.celery.app as celery_app_module

    celery_app_module = importlib.reload(celery_app_module)
    celery_app = celery_app_module.celery_app

    assert celery_app.conf.task_publish_retry is True
    assert celery_app.conf.task_publish_retry_policy == {
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.2,
    }
    assert celery_app.conf.broker_connection_timeout == 2.0
    assert celery_app.conf.redis_socket_connect_timeout == 2.0
    assert celery_app.conf.redis_socket_timeout == 2.0
    assert celery_app.conf.broker_transport_options == {
        "visibility_timeout": 123,
        "socket_connect_timeout": 2.0,
        "socket_timeout": 2.0,
    }
    assert celery_app.conf.task_default_queue == "test-agent-tasks"
