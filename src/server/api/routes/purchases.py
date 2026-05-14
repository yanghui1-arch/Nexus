"""Current-user purchase history API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.server.postgres.database import Database
from src.server.postgres.repositories import AgentPurchaseRepository
from src.server.schemas import AgentPurchaseResponse

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/purchases", response_model=list[AgentPurchaseResponse])
async def list_current_user_purchases(
    request: Request,
    client_id: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AgentPurchaseResponse]:
    """Return recent purchase records for the current client."""
    database: Database = request.app.state.database
    async with database.session() as session:
        purchases = await AgentPurchaseRepository.list_by_client_id(
            session,
            client_id=client_id,
            limit=limit,
        )
    return [AgentPurchaseResponse.from_record(purchase) for purchase in purchases]
