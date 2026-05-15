from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request

from src.logger import logger
from src.server.api.routes import agent_instances_router, auth_router, product_router, tasks_router
from src.server.config import get_settings
from src.server.github_feedback import GithubFeedbackPoller
from src.server.postgres.database import Database
from src.server.product_discovery import ProductDiscoveryPoller
from src.server.product_workflow import ProductWorkflowPoller
from src.server.redis.client import RedisClient
from src.server.runner import AgentTaskRunner


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = Database(settings.database_url)
    await database.connect()
    await database.create_schema()

    redis_client = RedisClient(
        settings.redis_url,
        ttl_seconds=settings.redis_message_ttl_seconds,
    )
    await redis_client.connect()

    runner = AgentTaskRunner(
        settings=settings,
        database=database,
    )
    github_feedback_poller = GithubFeedbackPoller(
        settings=settings,
        database=database,
        runner=runner,
    )
    product_discovery_poller = ProductDiscoveryPoller(
        settings=settings,
        database=database,
        runner=runner,
    )
    product_workflow_poller = ProductWorkflowPoller(
        settings=settings,
        database=database,
        runner=runner,
    )

    app.state.database = database
    app.state.redis_client = redis_client
    app.state.runner = runner
    app.state.github_feedback_poller = github_feedback_poller
    app.state.product_discovery_poller = product_discovery_poller
    app.state.product_workflow_poller = product_workflow_poller

    recovered_count = await runner.recover_unfinished_tasks()
    if recovered_count:
        logger.warning("Startup recovery scheduled %s unfinished tasks.", recovered_count)
    github_feedback_poller.start()
    product_discovery_poller.start()
    product_workflow_poller.start()

    try:
        yield
    finally:
        await product_workflow_poller.stop()
        await product_discovery_poller.stop()
        await github_feedback_poller.stop()
        await runner.shutdown()
        await redis_client.close()
        await database.disconnect()

        try:
            from src.sandbox import get_sandbox_pool_manager
        except ModuleNotFoundError:
            return

        await get_sandbox_pool_manager().shutdown()


app = FastAPI(
    title="Nexus Service",
    version="0.1.0-beta",
    lifespan=lifespan,
)

app.include_router(agent_instances_router)
app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(product_router)


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    db_ok = await request.app.state.database.ping()
    redis_ok = await request.app.state.redis_client.ping()
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "database": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }
