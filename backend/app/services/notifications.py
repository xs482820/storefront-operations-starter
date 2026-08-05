from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_runtime import CustomerNotification
from app.models.order import Order
from app.services.wechat_subscribe import send_miniapp_subscription_message


async def create_customer_notification(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    summary: str,
    kind: str = "system",
    route: str | None = None,
    unread: bool = True,
    push_event_key: str | None = None,
    push_payload: dict[str, Any] | None = None,
) -> CustomerNotification:
    row = CustomerNotification(
        user_id=user_id,
        title=title[:128],
        summary=summary[:255],
        kind=kind[:32],
        route=route[:255] if route else None,
        unread=unread,
    )
    db.add(row)
    await db.flush()
    if push_event_key:
        await send_miniapp_subscription_message(
            db,
            user_id=user_id,
            event_key=push_event_key,
            payload=push_payload or {},
        )
    return row


async def notify_order_customer(
    db: AsyncSession,
    *,
    order: Order,
    title: str,
    summary: str,
    route: str | None = None,
    kind: str = "order",
    push_event_key: str | None = None,
    push_payload: dict[str, Any] | None = None,
) -> CustomerNotification | None:
    if not order.customer_id:
        return None
    return await create_customer_notification(
        db,
        user_id=order.customer_id,
        title=title,
        summary=summary,
        kind=kind,
        route=route or f"/pages/order/detail?id={order.id}",
        push_event_key=push_event_key,
        push_payload=push_payload,
    )
