from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.server import background_services


class FakeBackgroundService:
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


async def _run_background_services_test():
    fake_database = FakeDatabase()
    fake_runner = FakeRunner()
    fake_services = [
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
    ]
    settings = SimpleNamespace(database_url="postgresql://example")

    with patch("src.server.background_services.get_settings", return_value=settings), patch(
        "src.server.background_services.Database", return_value=fake_database
    ), patch("src.server.background_services.AgentTaskRunner", return_value=fake_runner), patch(
        "src.server.background_services.GithubFeedbackPoller", return_value=fake_services[0]
    ), patch("src.server.background_services.ProductDiscoveryPoller", return_value=fake_services[1]), patch(
        "src.server.background_services.ProductWorkflowPoller", return_value=fake_services[2]
    ), patch(
        "src.server.background_services.AssistantPoller", return_value=fake_services[3]
    ), patch(
        "src.server.background_services.DiscordGateway", return_value=fake_services[4]
    ), patch("src.server.background_services.asyncio.Event", AutoStopEvent):
        await background_services.run_background_services()

    assert fake_database.connected is True
    assert fake_database.schema_created is True
    assert fake_database.disconnected is True
    assert fake_runner.closed is True
    assert [service.started for service in fake_services] == [True, True, True, True, True]
    assert [service.stopped for service in fake_services] == [True, True, True, True, True]


def test_run_background_services_owns_service_lifecycle():
    asyncio.run(_run_background_services_test())


async def _run_background_services_continues_when_discord_fails_to_start_test():
    fake_database = FakeDatabase()
    fake_runner = FakeRunner()
    fake_services = [
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
    ]
    failing_discord = FakeBackgroundService()

    def fail_discord_start():
        failing_discord.started = True
        raise RuntimeError("discord handler missing")

    failing_discord.start = fail_discord_start
    settings = SimpleNamespace(database_url="postgresql://example")

    with patch("src.server.background_services.get_settings", return_value=settings), patch(
        "src.server.background_services.Database", return_value=fake_database
    ), patch("src.server.background_services.AgentTaskRunner", return_value=fake_runner), patch(
        "src.server.background_services.GithubFeedbackPoller", return_value=fake_services[0]
    ), patch("src.server.background_services.ProductDiscoveryPoller", return_value=fake_services[1]), patch(
        "src.server.background_services.ProductWorkflowPoller", return_value=fake_services[2]
    ), patch(
        "src.server.background_services.AssistantPoller", return_value=fake_services[3]
    ), patch(
        "src.server.background_services.DiscordGateway", return_value=failing_discord
    ), patch("src.server.background_services.asyncio.Event", AutoStopEvent):
        await background_services.run_background_services()

    assert [service.started for service in fake_services] == [True, True, True, True]
    assert [service.stopped for service in fake_services] == [True, True, True, True]
    assert failing_discord.started is True
    assert failing_discord.stopped is False
    assert fake_database.disconnected is True
    assert fake_runner.closed is True


def test_run_background_services_continues_when_discord_fails_to_start():
    asyncio.run(_run_background_services_continues_when_discord_fails_to_start_test())


async def _run_background_services_continues_when_discord_fails_to_initialize_test():
    fake_database = FakeDatabase()
    fake_runner = FakeRunner()
    fake_services = [
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
        FakeBackgroundService(),
    ]
    settings = SimpleNamespace(database_url="postgresql://example")

    with patch("src.server.background_services.get_settings", return_value=settings), patch(
        "src.server.background_services.Database", return_value=fake_database
    ), patch("src.server.background_services.AgentTaskRunner", return_value=fake_runner), patch(
        "src.server.background_services.GithubFeedbackPoller", return_value=fake_services[0]
    ), patch("src.server.background_services.ProductDiscoveryPoller", return_value=fake_services[1]), patch(
        "src.server.background_services.ProductWorkflowPoller", return_value=fake_services[2]
    ), patch(
        "src.server.background_services.AssistantPoller", return_value=fake_services[3]
    ), patch(
        "src.server.background_services.DiscordGateway", side_effect=ValueError("handler missing")
    ), patch("src.server.background_services.asyncio.Event", AutoStopEvent):
        await background_services.run_background_services()

    assert [service.started for service in fake_services] == [True, True, True, True]
    assert [service.stopped for service in fake_services] == [True, True, True, True]
    assert fake_database.disconnected is True
    assert fake_runner.closed is True


def test_run_background_services_continues_when_discord_fails_to_initialize():
    asyncio.run(_run_background_services_continues_when_discord_fails_to_initialize_test())


def test_main_runs_background_services():
    with patch(
        "src.server.background_services.run_background_services",
        new_callable=AsyncMock,
    ) as run_background_services:
        background_services.main()

    run_background_services.assert_awaited_once_with()
