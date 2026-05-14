from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from src.server.postgres.repositories import AccountRepository
from src.server.schemas import AccountOverviewResponse

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.get("/overview", response_model=AccountOverviewResponse)
async def get_account_overview(
    request: Request,
    x_github_user_id: str | None = Header(default=None),
) -> AccountOverviewResponse:
    if not x_github_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        github_id = int(x_github_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid GitHub user id") from exc

    async with request.app.state.database.session() as session:
        account = await AccountRepository.get_by_github_id(session, github_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        entitlements = await AccountRepository.list_entitlements(session, github_id)

    return AccountOverviewResponse.from_record(
        account,
        entitlements,
        now=datetime.now(timezone.utc),
    )
