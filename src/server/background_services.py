from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

from src.channels.discord import DiscordGateway
from src.server.services.background import BackgroundService
from src.logger import logger
from src.server.assistant_poller import AssistantPoller
from src.server.config import get_settings
from src.server.github_feedback import GithubFeedbackPoller
from src.server.postgres.database import Database
from src.server.product_discovery import ProductDiscoveryPoller
from src.server.product_workflow import ProductWorkflowPoller
from src.server.runner import AgentTaskRunner
from src.server.services.assistant_discord import AssistantDiscordMessageHandler


async def run_background_services() -> None:
    """Run singleton background services until the process is stopped."""
    settings = get_settings()
    database = Database(settings.database_url)
    await database.connect()
    await database.create_schema()
    runner = AgentTaskRunner(settings=settings, database=database)
    services: list[BackgroundService] = [
        GithubFeedbackPoller(settings=settings, database=database, runner=runner),
        ProductDiscoveryPoller(settings=settings, database=database, runner=runner),
        ProductWorkflowPoller(settings=settings, database=database, runner=runner),
        AssistantPoller(settings=settings, database=database, runner=runner),
    ]
    try:
        services.append(
            DiscordGateway(
                settings=settings,
                handler=AssistantDiscordMessageHandler(settings=settings, database=database),
            )
        )
    except Exception:
        logger.exception("Discord Gateway failed to initialize; other background services will continue.")

    for service in services:
        if not isinstance(service, BackgroundService):
            raise TypeError(f"{service.__class__.__name__} does not implement BackgroundService.")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)

    try:
        started_services: list[BackgroundService] = []
        for service in services:
            try:
                service.start()
            except Exception:
                logger.exception(
                    "%s failed to start; other background services will continue.",
                    service.__class__.__name__,
                )
                continue
            started_services.append(service)
        logger.info("Nexus background services process starts.")
        await stop_event.wait()
    finally:
        for service in reversed(started_services):
            try:
                await service.stop()
            except Exception:
                logger.exception("%s failed to stop cleanly.", service.__class__.__name__)
        await runner.shutdown()
        await database.disconnect()
        logger.info("Nexus background services process stops.")


def main() -> None:
    """Start the singleton background services process."""
    asyncio.run(run_background_services())


if __name__ == "__main__":
    main()
