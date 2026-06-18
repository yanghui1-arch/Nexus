from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.server import pollers


class FakePoller:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


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


class FakeRunner:
    def __init__(self):
        self.closed = False

    async def shutdown(self):
        self.closed = True


class AutoStopEvent:
    def set(self):
        pass

    async def wait(self):
        return None


async def _run_pollers_test():
    fake_database = FakeDatabase()
    fake_runner = FakeRunner()
    fake_pollers = [FakePoller(), FakePoller(), FakePoller()]
    settings = SimpleNamespace(database_url="postgresql://example")

    with patch("src.server.pollers.get_settings", return_value=settings), patch(
        "src.server.pollers.Database", return_value=fake_database
    ), patch("src.server.pollers.AgentTaskRunner", return_value=fake_runner), patch(
        "src.server.pollers.GithubFeedbackPoller", return_value=fake_pollers[0]
    ), patch("src.server.pollers.ProductDiscoveryPoller", return_value=fake_pollers[1]), patch(
        "src.server.pollers.ProductWorkflowPoller", return_value=fake_pollers[2]
    ), patch("src.server.pollers.asyncio.Event", AutoStopEvent):
        await pollers.run_pollers()

    assert fake_database.connected is True
    assert fake_database.schema_created is True
    assert fake_database.disconnected is True
    assert fake_runner.closed is True
    assert [poller.started for poller in fake_pollers] == [True, True, True]
    assert [poller.stopped for poller in fake_pollers] == [True, True, True]


def test_run_pollers_owns_poller_lifecycle():
    asyncio.run(_run_pollers_test())


def test_main_runs_pollers():
    with patch("src.server.pollers.run_pollers", new_callable=AsyncMock) as run_pollers:
        pollers.main()

    run_pollers.assert_awaited_once_with()
