from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.server.api.main import lifespan


class FakePoller:
    def __init__(self):
        """Initialize the test helper."""
        self.started = False
        self.stopped = False
        self.stop = AsyncMock(side_effect=self._stop)

    def start(self):
        """Start a fake service."""
        self.started = True

    async def _stop(self):
        """Stop a fake service."""
        self.stopped = True


class FakeRunner:
    async def recover_unfinished_tasks(self):
        """Return recovered task count."""
        return 0

    async def shutdown(self):
        """Shut down a fake service."""
        return None


class FakeDatabase:
    async def connect(self):
        """Connect a fake service."""
        return None

    async def create_schema(self):
        """Create a fake schema."""
        return None

    async def disconnect(self):
        """Disconnect a fake service."""
        return None

    async def ping(self):
        """Return the fake service health status."""
        return True


class FakeRedis:
    async def connect(self):
        """Connect a fake service."""
        return None

    async def close(self):
        """Close a fake service."""
        return None

    async def ping(self):
        """Return the fake service health status."""
        return True


class FakeApp:
    def __init__(self):
        """Initialize the test helper."""
        self.state = SimpleNamespace()


async def _run_lifespan_test():
    """Run the application lifespan test harness."""
    app = FakeApp()
    fake_runner = FakeRunner()
    fake_poller = FakePoller()
    fake_workflow_poller = FakePoller()
    settings = SimpleNamespace(
        database_url="postgresql://example",
        redis_url="redis://example",
        redis_message_ttl_seconds=60,
    )

    with patch("src.server.api.main.get_settings", return_value=settings), patch(
        "src.server.api.main.Database", return_value=FakeDatabase()
    ), patch("src.server.api.main.RedisClient", return_value=FakeRedis()), patch(
        "src.server.api.main.AgentTaskRunner", return_value=fake_runner
    ), patch(
        "src.server.api.main.GithubFeedbackPoller",
        return_value=SimpleNamespace(start=lambda: None, stop=AsyncMock()),
    ), patch("src.server.api.main.ProductDiscoveryPoller", return_value=fake_poller), patch(
        "src.server.api.main.ProductWorkflowPoller", return_value=fake_workflow_poller
    ):
        async with lifespan(app):
            assert app.state.product_discovery_poller is fake_poller
            assert app.state.product_workflow_poller is fake_workflow_poller
            assert fake_poller.started is True
            assert fake_workflow_poller.started is True

    assert fake_poller.stopped is True
    assert fake_workflow_poller.stopped is True


def test_lifespan_attaches_product_discovery_poller():
    """Verify lifespan attaches product discovery poller."""
    asyncio.run(_run_lifespan_test())
