from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from src.server.api.main import lifespan


class FakeRunner:
    def __init__(self):
        self.closed = False

    async def shutdown(self):
        self.closed = True


class FakeDatabase:
    def __init__(self):
        self.connected = False
        self.schema_created = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def create_schema(self):
        self.schema_created = True

    async def disconnect(self):
        self.disconnected = True

    async def ping(self):
        return True


class FakeRedis:
    def __init__(self):
        self.connected = False
        self.closed = False

    async def connect(self):
        self.connected = True

    async def close(self):
        self.closed = True

    async def ping(self):
        return True


class FakeApp:
    def __init__(self):
        self.state = SimpleNamespace()


async def _run_lifespan_test():
    app = FakeApp()
    fake_database = FakeDatabase()
    fake_redis = FakeRedis()
    fake_runner = FakeRunner()
    settings = SimpleNamespace(
        database_url="postgresql://example",
        redis_url="redis://example",
        redis_message_ttl_seconds=60,
    )

    with patch("src.server.api.main.get_settings", return_value=settings), patch(
        "src.server.api.main.Database", return_value=fake_database
    ), patch("src.server.api.main.RedisClient", return_value=fake_redis), patch(
        "src.server.api.main.AgentTaskRunner", return_value=fake_runner
    ):
        async with lifespan(app):
            assert app.state.database is fake_database
            assert app.state.redis_client is fake_redis
            assert app.state.runner is fake_runner
            assert not hasattr(app.state, "product_discovery_poller")
            assert not hasattr(app.state, "product_workflow_poller")

    assert fake_database.connected is True
    assert fake_database.schema_created is True
    assert fake_database.disconnected is True
    assert fake_redis.connected is True
    assert fake_redis.closed is True
    assert fake_runner.closed is True


def test_lifespan_does_not_start_pollers():
    asyncio.run(_run_lifespan_test())
