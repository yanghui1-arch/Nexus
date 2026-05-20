from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from src.server.config import get_settings
from src.server.postgres.database import Database
from src.server.postgres.models import UserRecord
from src.server.postgres.repositories import AuthSessionRepository


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_current_user(request: Request) -> UserRecord:
    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    database: Database = request.app.state.database
    async with database.session() as session:
        user = await AuthSessionRepository.get_user_by_token_hash(session, hash_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user
