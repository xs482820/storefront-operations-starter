from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin-users-extra"])


@router.get("/users/avatar-map", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_users_avatar_map(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_ids: str = Query(default="", max_length=2000),
) -> dict:
    raw_ids = [item.strip() for item in user_ids.split(",")]
    ids: list[int] = []
    for item in raw_ids:
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if value > 0:
            ids.append(value)
        if len(ids) >= 200:
            break

    if not ids:
        return {"items": []}

    rows = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(ids))
        )
    ).all()
    avatar_map = {
        row.id: (row.profile.avatar_url if row.profile and row.profile.avatar_url else None)
        for row in rows
    }
    return {
        "items": [
            {"user_id": user_id, "avatar_url": avatar_map.get(user_id)}
            for user_id in ids
        ]
    }

