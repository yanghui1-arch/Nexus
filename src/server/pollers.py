from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

from src.logger import logger
from src.server.config import get_settings
from src.server.github_feedback import GithubFeedbackPoller
from src.server.postgres.database import Database
from src.server.product_discovery import ProductDiscoveryPoller
from src.server.product_workflow import ProductWorkflowPoller
from src.server.runner import AgentTaskRunner
from src.server.secretary import SecretaryPoller


async def run_pollers() -> None:
    """Run the singleton poller group until the process is stopped."""
    settings = get_settings()
    database = Database(settings.database_url)
    await database.connect()
    await database.create_schema()
    runner = AgentTaskRunner(settings=settings, database=database)
    pollers = [
        GithubFeedbackPoller(settings=settings, database=database, runner=runner),
        ProductDiscoveryPoller(settings=settings, database=database, runner=runner),
        ProductWorkflowPoller(settings=settings, database=database, runner=runner),
        SecretaryPoller(settings=settings, database=database, runner=runner),
    ]
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)

    try:
        for poller in pollers:
            poller.start()
        logger.info("Nexus poller process starts.")
        await stop_event.wait()
    finally:
        for poller in reversed(pollers):
            await poller.stop()
        await runner.shutdown()
        await database.disconnect()
        logger.info("Nexus poller process stops.")


def main() -> None:
    """Start the singleton poller process."""
    asyncio.run(run_pollers())


if __name__ == "__main__":
    main()
