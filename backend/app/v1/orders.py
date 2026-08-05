from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductSKU, Unit
from app.models.user import User
from app.schemas.order import (
    OrderAutoCloseOut,
    OrderCreateIn,
    OrderCreateOut,
    OrderDetailOut,
    OrderItemOut,
    OrderShipConfirmIn,
    ShippingQuoteIn,
    ShippingQuoteOut,
    OrderStatusUpdateIn,
)
from app.services.orders import apply_status_transition, create_order, resolve_customer_for_order
from app.services.shipping import calculate_shipping_fee

router = APIRouter(prefix="/orders", tags=["orders"])
settings = get_settings()


def _serialize_order_detail(
    order: Order,
    items: list[OrderItem],
    labels: dict[tuple[int, int], dict] | None = None,
) -> OrderDetailOut:
    labels = labels or {}
    freight_amount = None if order.freight_amount is None else str(order.freight_amount)
    return OrderDetailOut(
        order_no=order.order_no,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=str(order.total_amount),
        discount_amount=str(order.discount_amount),
        shipping_fee=str(order.shipping_fee),
        shipping_policy=order.shipping_policy,
        shipping_province=order.shipping_province,
        shipping_city=order.shipping_city,
        shipping_district=order.shipping_district,
        shipping_address=order.shipping_address,
        shipping_recipient=order.shipping_recipient,
        shipping_phone=order.shipping_phone,
        logistics_company=order.logistics_company,
        tracking_no=order.tracking_no,
        shipping_method=order.shipping_method,
        shipping_scene_images=order.shipping_scene_images or [],
        freight_payer=order.freight_payer,
        freight_paid_by_us=order.freight_paid_by_us,
        freight_amount=freight_amount,
        freight_payment_images=order.freight_payment_images or [],
        shipped_at=order.shipped_at.isoformat() if order.shipped_at else None,
        payable_amount=str(order.payable_amount),
        created_at=order.created_at.isoformat(),
        items=[
            OrderItemOut(
                sku_id=item.sku_id,
                unit_id=item.unit_id,
                product_name=labels.get((item.sku_id, item.unit_id), {}).get("product_name"),
                sku_name=labels.get((item.sku_id, item.unit_id), {}).get("sku_name"),
                sku_code=labels.get((item.sku_id, item.unit_id), {}).get("sku_code"),
                unit_code=labels.get((item.sku_id, item.unit_id), {}).get("unit_code"),
                unit_name=labels.get((item.sku_id, item.unit_id), {}).get("unit_name"),
                quantity=item.quantity,
                base_quantity=item.base_quantity,
                unit_price=str(item.unit_price),
                line_amount=str(item.line_amount),
            )
            for item in items
        ],
    )


@router.post(
    "/{order_no}/ship-confirm",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def ship_confirm_order(
    order_no: str,
    payload: OrderShipConfirmIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if not order:
        raise not_found("order not found")

    if order.status == OrderStatus.PAID:
        order = await apply_status_transition(db=db, order=order, target_status=OrderStatus.PICKING, actor=current_user)
    if order.status != OrderStatus.PICKING:
        raise not_found("order must be in picking status before ship confirm")

    order.logistics_company = payload.logistics_company
    order.tracking_no = payload.tracking_no
    order.shipping_method = payload.shipping_method
    order.shipping_scene_images = payload.shipping_scene_images
    order.freight_payer = payload.freight_payer
    order.freight_paid_by_us = payload.freight_paid_by_us
    order.freight_amount = payload.freight_amount
    order.freight_payment_images = payload.freight_payment_images
    if payload.note:
        order.note = payload.note

    order = await apply_status_transition(db=db, order=order, target_status=OrderStatus.SHIPPED, actor=current_user)
    order.shipped_at = datetime.now(UTC)
    await db.commit()
    return {
        "order_no": order.order_no,
        "status": order.status.value,
        "logistics_company": order.logistics_company,
        "tracking_no": order.tracking_no,
        "shipping_scene_image_count": len(order.shipping_scene_images or []),
        "freight_payment_image_count": len(order.freight_payment_images or []),
    }


@router.post("", response_model=OrderCreateOut)
async def create_order_endpoint(
    payload: OrderCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderCreateOut:
    customer = await resolve_customer_for_order(db=db, payload=payload, actor=current_user)
    order = await create_order(db=db, payload=payload, customer=customer, actor=current_user)
    await db.commit()
    return OrderCreateOut(
        order_no=order.order_no,
        status=order.status,
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        shipping_fee=order.shipping_fee,
        shipping_policy=order.shipping_policy,
        payable_amount=order.payable_amount,
    )


@router.patch(
    "/{order_no}/status",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def update_order_status(
    order_no: str,
    payload: OrderStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if not order:
        raise not_found("order not found")
    order = await apply_status_transition(db=db, order=order, target_status=payload.status, actor=current_user)
    await db.commit()
    return {"order_no": order.order_no, "status": order.status.value}


@router.get("/{order_no}", response_model=OrderDetailOut)
async def get_order(
    order_no: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderDetailOut:
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if not order:
        raise not_found("order not found")

    if current_user.role not in {UserRole.ADMIN, UserRole.EMPLOYEE} and order.customer_id != current_user.id:
        raise not_found("order not found")

    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    labels: dict[tuple[int, int], dict] = {}
    if items:
        sku_ids = sorted({item.sku_id for item in items})
        unit_ids = sorted({item.unit_id for item in items})
        sku_rows = (
            await db.execute(
                select(ProductSKU.id, Product.name, ProductSKU.sku_name, ProductSKU.sku_code)
                .join(Product, Product.id == ProductSKU.product_id)
                .where(ProductSKU.id.in_(sku_ids))
            )
        ).all()
        unit_rows = (
            await db.execute(
                select(Unit.id, Unit.code, Unit.name)
                .where(Unit.id.in_(unit_ids))
            )
        ).all()
        sku_meta = {
            row[0]: {"product_name": row[1], "sku_name": row[2], "sku_code": row[3]}
            for row in sku_rows
        }
        unit_meta = {
            row[0]: {"unit_code": row[1], "unit_name": row[2]}
            for row in unit_rows
        }
        for item in items:
            labels[(item.sku_id, item.unit_id)] = {
                **sku_meta.get(item.sku_id, {}),
                **unit_meta.get(item.unit_id, {}),
            }
    return _serialize_order_detail(order, list(items), labels)


@router.get("")
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    stmt = select(Order).order_by(Order.id.desc()).limit(100)
    if current_user.role not in {UserRole.ADMIN, UserRole.EMPLOYEE}:
        stmt = stmt.where(Order.customer_id == current_user.id)
    orders = (await db.scalars(stmt)).all()
    return [
        {
            "order_no": order.order_no,
            "status": order.status.value,
            "customer_id": order.customer_id,
            "total_amount": str(order.total_amount),
            "discount_amount": str(order.discount_amount),
            "shipping_fee": str(order.shipping_fee),
            "shipping_policy": order.shipping_policy,
            "logistics_company": order.logistics_company,
            "tracking_no": order.tracking_no,
            "shipping_method": order.shipping_method,
            "shipping_scene_image_count": len(order.shipping_scene_images or []),
            "freight_payer": order.freight_payer,
            "freight_paid_by_us": order.freight_paid_by_us,
            "freight_amount": str(order.freight_amount) if order.freight_amount is not None else None,
            "freight_payment_image_count": len(order.freight_payment_images or []),
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
            "payable_amount": str(order.payable_amount),
            "note": order.note,
            "created_at": order.created_at.isoformat(),
        }
        for order in orders
    ]


@router.post(
    "/{order_no}/mock-pay",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def mock_pay_order(
    order_no: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        return {"order_no": order_no, "status": order.status.value, "message": "no change"}
    order.status = OrderStatus.PAID
    await db.commit()
    return {"order_no": order_no, "status": order.status.value}


@router.post("/{order_no}/cancel")
async def cancel_order(
    order_no: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if not order:
        raise not_found("order not found")
    if current_user.role not in {UserRole.ADMIN, UserRole.EMPLOYEE} and order.customer_id != current_user.id:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("only pending_payment order can be canceled")

    order = await apply_status_transition(db=db, order=order, target_status=OrderStatus.CANCELED, actor=current_user)
    await db.commit()
    return {"order_no": order.order_no, "status": order.status.value}


@router.post(
    "/auto-close-expired",
    response_model=OrderAutoCloseOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def auto_close_expired_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    cutoff_minutes: int = Query(default=30, ge=1, le=24 * 60),
    batch_size: int = Query(default=200, ge=1, le=1000),
) -> OrderAutoCloseOut:
    cutoff_time = datetime.now(UTC) - timedelta(minutes=cutoff_minutes)
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.status == OrderStatus.PENDING_PAYMENT, Order.created_at < cutoff_time)
            .order_by(Order.id.asc())
            .limit(batch_size)
        )
    ).all()
    closed_order_nos: list[str] = []
    for order in orders:
        order = await apply_status_transition(
            db=db,
            order=order,
            target_status=OrderStatus.CANCELED,
            actor=current_user,
        )
        closed_order_nos.append(order.order_no)

    if closed_order_nos:
        await db.commit()
    return OrderAutoCloseOut(
        cutoff_minutes=cutoff_minutes,
        scanned=len(orders),
        closed=len(closed_order_nos),
        closed_order_nos=closed_order_nos,
    )


@router.post("/shipping-quote", response_model=ShippingQuoteOut)
async def get_shipping_quote(
    payload: ShippingQuoteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShippingQuoteOut:
    customer = current_user
    if payload.customer_id is not None and current_user.role in {UserRole.ADMIN, UserRole.EMPLOYEE}:
        candidate = await db.get(User, payload.customer_id)
        if candidate:
            customer = candidate
    remote_keywords = [k.strip() for k in settings.SHIPPING_REMOTE_KEYWORDS.split(",") if k.strip()]
    shipping_fee, shipping_policy = calculate_shipping_fee(
        role=customer.role,
        merchandise_amount=payload.merchandise_amount,
        province=payload.shipping_province,
        city=payload.shipping_city,
        retail_free_threshold=settings.SHIPPING_RETAIL_FREE_THRESHOLD,
        retail_base_fee=settings.SHIPPING_RETAIL_BASE_FEE,
        wholesale_base_fee=settings.SHIPPING_WHOLESALE_BASE_FEE,
        remote_surcharge=settings.SHIPPING_REMOTE_SURCHARGE,
        remote_keywords=remote_keywords,
    )
    return ShippingQuoteOut(shipping_fee=shipping_fee, shipping_policy=shipping_policy)
