"""API route handlers."""

from src.server.api.routes.account import router as account_router
from src.server.api.routes.agent_instances import router as agent_instances_router
from src.server.api.routes.product import router as product_router
from src.server.api.routes.tasks import router as tasks_router

__all__ = ["account_router", "agent_instances_router", "product_router", "tasks_router"]
