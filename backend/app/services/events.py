from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_event import BusinessEvent
from app.models.user import User


def generate_event_no() -> str:
    return f"EVT{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _snapshot_actor(actor: User | None) -> tuple[int | None, str | None, str | None]:
    if not actor:
        return None, None, None
    actor_name = actor.profile.display_name if actor.profile and actor.profile.display_name else actor.username
    return actor.id, actor.role.value, actor_name


async def write_business_event(
    db: AsyncSession,
    *,
    entity_type: str,
    action_code: str,
    action_label: str,
    source: str = "system",
    entity_id: int | None = None,
    entity_no: str | None = None,
    actor: User | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
    evidence: dict | None = None,
    note: str | None = None,
    visibility: str = "internal",
    correlation_id: str | None = None,
    request_id: str | None = None,
) -> BusinessEvent:
    if request_id:
        existing = await db.scalar(select(BusinessEvent).where(BusinessEvent.request_id == request_id))
        if existing:
            return existing

    actor_user_id, actor_role, actor_name_snapshot = _snapshot_actor(actor)
    row = BusinessEvent(
        event_no=generate_event_no(),
        entity_type=entity_type,
        entity_id=entity_id,
        entity_no=entity_no,
        action_code=action_code,
        action_label=action_label,
        source=source,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_name_snapshot=actor_name_snapshot,
        visibility=visibility,
        correlation_id=correlation_id,
        request_id=request_id or uuid4().hex,
        before_data=before_data or {},
        after_data=after_data or {},
        evidence=evidence or {},
        note=note,
    )
    db.add(row)
    await db.flush()
    return row


async def list_business_events(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    entity_no: str | None = None,
    action_prefix: str | None = None,
    action_contains: str | None = None,
    limit: int = 100,
) -> list[BusinessEvent]:
    stmt = select(BusinessEvent).order_by(desc(BusinessEvent.id)).limit(limit)
    if entity_type:
        stmt = stmt.where(BusinessEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(BusinessEvent.entity_id == entity_id)
    if entity_no:
        stmt = stmt.where(BusinessEvent.entity_no == entity_no)
    if action_prefix:
        stmt = stmt.where(BusinessEvent.action_code.startswith(action_prefix))
    if action_contains:
        stmt = stmt.where(BusinessEvent.action_code.contains(action_contains))
    rows = (await db.scalars(stmt)).all()
    return list(rows)
