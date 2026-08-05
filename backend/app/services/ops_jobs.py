from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus, PaymentMethod, ShippingMode, SystemLogCategory, UserRole
from app.models.order import Order
from app.services.orders import cancel_order, complete_order
from app.services.system_logs import write_system_log


async def auto_cancel_expired_orders(
    db: AsyncSession,
    cutoff_minutes: int = 10,
    batch_size: int = 200,
) -> list[str]:
    cutoff_time = datetime.now(UTC) - timedelta(minutes=cutoff_minutes)
    rows = (
        await db.scalars(
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING_PAYMENT,
                Order.created_at < cutoff_time,
            )
            .order_by(Order.id.asc())
            .limit(batch_size)
        )
    ).all()

    canceled: list[str] = []
    for order in rows:
        if order.buyer_role == UserRole.WHOLESALE and order.payment_method == PaymentMethod.OFFLINE_TRANSFER:
            continue
        await cancel_order(db=db, order=order, note="超过支付时限，订单已自动取消", cancellation_source="auto_timeout")
        canceled.append(order.order_no)
        await write_system_log(
            db=db,
            category=SystemLogCategory.ORDER,
            action="auto_canceled",
            order_no=order.order_no,
            message="System auto-canceled unpaid order",
            details={"cutoff_minutes": cutoff_minutes},
        )
    return canceled


async def cancel_order_if_expired(
    db: AsyncSession,
    order: Order,
    cutoff_minutes: int = 10,
    note: str = "超过支付时限，订单已自动取消",
) -> bool:
    if order.status != OrderStatus.PENDING_PAYMENT:
        return False
    if order.buyer_role == UserRole.WHOLESALE and order.payment_method == PaymentMethod.OFFLINE_TRANSFER:
        return False
    if order.created_at >= datetime.now(UTC) - timedelta(minutes=cutoff_minutes):
        return False

    # ponytail: scheduler is primary; this guard covers stale orders touched before the next scheduler tick.
    await cancel_order(db=db, order=order, note=note, cancellation_source="auto_timeout")
    await write_system_log(
        db=db,
        category=SystemLogCategory.ORDER,
        action="auto_canceled",
        order_no=order.order_no,
        message="System auto-canceled unpaid order on access",
        details={"cutoff_minutes": cutoff_minutes},
    )
    return True


async def auto_complete_shipped_orders(
    db: AsyncSession,
    express_days: int = 3,
    offline_days: int = 10,
    batch_size: int = 500,
) -> list[str]:
    now = datetime.now(UTC)
    rows = (
        await db.scalars(
            select(Order)
            .where(Order.status == OrderStatus.SHIPPED)
            .order_by(Order.id.asc())
            .limit(batch_size)
        )
    ).all()

    completed: list[str] = []
    for order in rows:
        should_complete = False
        if order.shipping_mode == ShippingMode.EXPRESS and order.delivery_signed_at:
            should_complete = now >= order.delivery_signed_at + timedelta(days=express_days)
        elif order.shipping_mode == ShippingMode.OFFLINE and order.shipped_at:
            should_complete = now >= order.shipped_at + timedelta(days=offline_days)
        if not should_complete:
            continue
        await complete_order(db=db, order=order)
        completed.append(order.order_no)
        await write_system_log(
            db=db,
            category=SystemLogCategory.SCHEDULER,
            action="auto_completed",
            order_no=order.order_no,
            message="System Auto-completed shipped order",
            details={
                "shipping_mode": order.shipping_mode.value if order.shipping_mode else None,
                "express_days": express_days,
                "offline_days": offline_days,
            },
        )
    return completed
