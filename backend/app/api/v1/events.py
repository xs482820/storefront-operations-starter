from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.event import BusinessEventOut
from app.services.events import list_business_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[BusinessEventOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = Query(default=None, max_length=32),
    entity_id: int | None = Query(default=None, ge=1),
    entity_no: str | None = Query(default=None, max_length=64),
    action_prefix: str | None = Query(default=None, max_length=48),
    action_contains: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[BusinessEventOut]:
    rows = await list_business_events(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_no=entity_no,
        action_prefix=action_prefix,
        action_contains=action_contains,
        limit=limit,
    )
    return [
        BusinessEventOut(
            id=row.id,
            event_no=row.event_no,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            entity_no=row.entity_no,
            action_code=row.action_code,
            action_label=row.action_label,
            source=row.source,
            actor_user_id=row.actor_user_id,
            actor_role=row.actor_role,
            actor_name_snapshot=row.actor_name_snapshot,
            visibility=row.visibility,
            correlation_id=row.correlation_id,
            request_id=row.request_id,
            before_data=row.before_data,
            after_data=row.after_data,
            evidence=row.evidence,
            note=row.note,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
