"""API route handlers."""

from src.server.api.routes.agent_instances import router as agent_instances_router
from src.server.api.routes.product import router as product_router
from src.server.api.routes.purchases import router as purchases_router
from src.server.api.routes.tasks import router as tasks_router

__all__ = ["agent_instances_router", "product_router", "purchases_router", "tasks_router"]
