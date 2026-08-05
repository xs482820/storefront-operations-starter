from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.aftersale import AfterSaleRequest
from app.models.enums import AfterSaleStatus, AfterSaleType, UserRole
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.enums import OrderStatus, PaymentStatus
from app.models.user import User
from app.schemas.aftersale import AfterSaleCreateIn, AfterSaleOut, AfterSaleStatusUpdateIn
from app.services.inventory import restore_by_base
from app.services.orders import release_order_reservations

router = APIRouter(prefix="/aftersales", tags=["aftersales"])
settings = get_settings()

ALLOWED_AFTERSALE_TRANSITIONS: dict[AfterSaleStatus, set[AfterSaleStatus]] = {
    AfterSaleStatus.PENDING: {AfterSaleStatus.APPROVED, AfterSaleStatus.REJECTED},
    AfterSaleStatus.APPROVED: {AfterSaleStatus.COMPLETED, AfterSaleStatus.REJECTED},
    AfterSaleStatus.REJECTED: set(),
    AfterSaleStatus.COMPLETED: set(),
}


def generate_request_no() -> str:
    return f"AS{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _serialize(item: AfterSaleRequest, order_no: str) -> AfterSaleOut:
    amount = None if item.requested_amount is None else f"{item.requested_amount:.2f}"
    return AfterSaleOut(
        request_no=item.request_no,
        order_no=order_no,
        customer_id=item.customer_id,
        request_type=item.request_type,
        status=item.status,
        requested_amount=amount,
        reason=item.reason,
        note=item.note,
        created_at=item.created_at.isoformat(),
    )


@router.post("", response_model=AfterSaleOut)
async def create_aftersale(
    payload: AfterSaleCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AfterSaleOut:
    order = await db.scalar(select(Order).where(Order.order_no == payload.order_no))
    if not order:
        raise not_found("order not found")
    if current_user.role not in {UserRole.ADMIN, UserRole.EMPLOYEE} and order.customer_id != current_user.id:
        raise not_found("order not found")
    if order.status in {OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELED}:
        raise bad_request("order status does not support aftersale")

    requested_amount = Decimal(payload.requested_amount) if payload.requested_amount is not None else None
    if requested_amount is not None and requested_amount > Decimal(order.payable_amount):
        raise bad_request("requested_amount cannot exceed order payable amount")

    existing_active = await db.scalar(
        select(AfterSaleRequest.id).where(
            AfterSaleRequest.order_id == order.id,
            AfterSaleRequest.status.in_([AfterSaleStatus.PENDING, AfterSaleStatus.APPROVED]),
        )
    )
    if existing_active:
        raise bad_request("active aftersale request already exists for this order")

    request = AfterSaleRequest(
        request_no=generate_request_no(),
        order_id=order.id,
        customer_id=order.customer_id,
        request_type=payload.request_type,
        status=AfterSaleStatus.PENDING,
        requested_amount=requested_amount,
        reason=payload.reason,
        note=payload.note,
    )
    db.add(request)
    await db.commit()
    return _serialize(request, order.order_no)


@router.get("", response_model=list[AfterSaleOut])
async def list_aftersales(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AfterSaleOut]:
    stmt = (
        select(AfterSaleRequest, Order.order_no)
        .join(Order, Order.id == AfterSaleRequest.order_id)
        .order_by(desc(AfterSaleRequest.id))
        .limit(100)
    )
    if current_user.role not in {UserRole.ADMIN, UserRole.EMPLOYEE}:
        stmt = stmt.where(AfterSaleRequest.customer_id == current_user.id)
    rows = (await db.execute(stmt)).all()
    return [_serialize(item, order_no) for item, order_no in rows]


@router.patch(
    "/{request_no}/status",
    response_model=AfterSaleOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def update_aftersale_status(
    request_no: str,
    payload: AfterSaleStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AfterSaleOut:
    item = await db.scalar(select(AfterSaleRequest).where(AfterSaleRequest.request_no == request_no))
    if not item:
        raise not_found("aftersale request not found")
    order = await db.get(Order, item.order_id)
    if not order:
        raise not_found("order not found")
    if payload.status != item.status:
        allowed = ALLOWED_AFTERSALE_TRANSITIONS.get(item.status, set())
        if payload.status not in allowed:
            raise bad_request(f"invalid aftersale status transition: {item.status.value} -> {payload.status.value}")

    # For return/exchange, complete step triggers stock restore exactly once.
    if (
        payload.status == AfterSaleStatus.COMPLETED
        and item.request_type in {AfterSaleType.RETURN, AfterSaleType.EXCHANGE}
        and not item.stock_reverted
        ):
        order_items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
        for order_item in order_items:
            await restore_by_base(
                db=db,
                sku_id=order_item.sku_id,
                base_qty=order_item.base_quantity,
                note=f"aftersale {item.request_no} completed restore",
                order_no=order.order_no,
            )
        item.stock_reverted = True

    # Refund/return completion closes order and releases any remaining reservations.
    if payload.status == AfterSaleStatus.COMPLETED and item.request_type in {AfterSaleType.REFUND, AfterSaleType.RETURN}:
        if order.status != OrderStatus.CANCELED:
            await release_order_reservations(db=db, order=order)
            order.status = OrderStatus.CANCELED

        payment = await db.scalar(
            select(PaymentRecord)
            .where(PaymentRecord.order_id == order.id)
            .order_by(PaymentRecord.id.desc())
        )
        if payment and settings.WECHAT_PAY_MOCK and payment.status == PaymentStatus.PAID:
            payment.status = PaymentStatus.REFUNDED

    item.status = payload.status
    item.note = payload.note or item.note
    await db.commit()
    return _serialize(item, order.order_no)
