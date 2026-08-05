import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import bad_request, not_found
from app.models.enums import OrderStatus, PaymentMethod, SKUType, ShippingMode, StockChangeReason, UserRole
from app.models.order import Order, OrderItem
from app.models.product import ProductSKU
from app.models.user import User
from app.schemas.customer import CustomerOrderCreateIn
from app.services.inventory import change_online_stock
from app.services.events import write_business_event
from app.services.notifications import notify_order_customer
from app.services.shipping import calculate_shipping_fee
from app.services.wechat_shipping import upload_miniapp_shipping_info

logger = logging.getLogger(__name__)


def generate_order_no() -> str:
    return f"ORD{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _resolve_sku_type(role: UserRole) -> SKUType:
    return SKUType.WHOLESALE if role == UserRole.WHOLESALE else SKUType.RETAIL


async def _resolve_role_sku(db: AsyncSession, sku: ProductSKU, expected_sku_type: SKUType) -> ProductSKU:
    if sku.sku_type == expected_sku_type:
        return sku
    replacement = await db.scalar(
        select(ProductSKU)
        .options(selectinload(ProductSKU.product))
        .where(
            ProductSKU.product_id == sku.product_id,
            ProductSKU.sku_type == expected_sku_type,
            ProductSKU.spec_value_1 == sku.spec_value_1,
            ProductSKU.spec_value_2 == sku.spec_value_2,
            ProductSKU.is_active.is_(True),
        )
    )
    # ponytail: legacy products can have only one SKU type; the active role still controls price and minimum quantity.
    return replacement or sku


async def sync_wechat_shipping_upload(
    db: AsyncSession,
    order: Order,
    operator: User | None,
    source: str,
) -> dict:
    if order.wechat_shipping_status == "succeeded":
        return {"status": "succeeded", "reason": "already uploaded"}

    now = datetime.now(UTC)
    order.wechat_shipping_status = "pending"
    order.wechat_shipping_error = None
    order.wechat_shipping_attempted_at = now
    order.wechat_shipping_attempts = (order.wechat_shipping_attempts or 0) + 1
    await db.flush()

    try:
        result = await upload_miniapp_shipping_info(
            db=db,
            order=order,
            shipping_mode=order.shipping_mode or ShippingMode.OFFLINE,
            logistics_company=order.logistics_company,
            tracking_no=order.tracking_no,
            shipping_proof_url=order.shipping_proof_url,
        )
        if result.get("manual"):
            order.wechat_shipping_status = "manual_required"
            order.wechat_shipping_error = str(result.get("reason") or "manual entry is required")[:512]
            action_code = "order.wechat_shipping_manual_required"
            action_label = "微信发货需手工补录"
            status = "manual_required"
        elif result.get("skipped"):
            order.wechat_shipping_status = "skipped"
            order.wechat_shipping_error = str(result.get("reason") or "wechat shipping is not required")[:512]
            action_code = "order.wechat_shipping_skipped"
            action_label = "微信发货无需录入"
            status = "skipped"
        else:
            order.wechat_shipping_status = "succeeded"
            order.wechat_shipping_error = None
            order.wechat_shipping_uploaded_at = datetime.now(UTC)
            action_code = "order.wechat_shipping_uploaded"
            action_label = "微信发货录入"
            status = "succeeded"
        await write_business_event(
            db=db,
            entity_type="order",
            entity_id=order.id,
            entity_no=order.order_no,
            action_code=action_code,
            action_label=action_label,
            source=source,
            actor=operator,
            after_data={
                "wechat_shipping_status": order.wechat_shipping_status,
                "wechat_shipping_attempts": order.wechat_shipping_attempts,
            },
            evidence={"shipping_proof_url": order.shipping_proof_url} if order.shipping_proof_url else {},
            note=order.wechat_shipping_error,
        )
        return {"status": status, "reason": order.wechat_shipping_error}
    except Exception as error:
        error_text = str(error)[:512]
        order.wechat_shipping_status = "failed"
        order.wechat_shipping_error = error_text
        await write_business_event(
            db=db,
            entity_type="order",
            entity_id=order.id,
            entity_no=order.order_no,
            action_code="order.wechat_shipping_failed",
            action_label="微信发货录入失败",
            source=source,
            actor=operator,
            after_data={
                "wechat_shipping_status": order.wechat_shipping_status,
                "wechat_shipping_attempts": order.wechat_shipping_attempts,
            },
            note=error_text,
        )
        logger.warning("wechat mini shipping upload failed for order %s: %s", order.order_no, error_text)
        return {"status": "failed", "reason": error_text}


async def create_customer_order(
    db: AsyncSession,
    payload: CustomerOrderCreateIn,
    current_user: User,
) -> Order:
    if current_user.role not in {UserRole.RETAIL, UserRole.WHOLESALE, UserRole.EMPLOYEE}:
        raise bad_request("only customer accounts can create orders")
    requested_pricing_mode = payload.pricing_mode or (
        "wholesale" if current_user.role == UserRole.WHOLESALE else "retail"
    )
    effective_role = UserRole.WHOLESALE if requested_pricing_mode == "wholesale" else UserRole.RETAIL
    if effective_role == UserRole.WHOLESALE and current_user.role not in {UserRole.WHOLESALE, UserRole.EMPLOYEE}:
        raise bad_request("wholesale purchase is only available for wholesale users")
    if payload.payment_method == PaymentMethod.OFFLINE_TRANSFER and effective_role not in {UserRole.WHOLESALE, UserRole.EMPLOYEE}:
        raise bad_request("offline_transfer is only available for wholesale users")

    expected_sku_type = _resolve_sku_type(effective_role)
    original_amount = Decimal("0.00")
    line_items: list[tuple[ProductSKU, int, Decimal]] = []

    for item in payload.items:
        sku = await db.scalar(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id == item.sku_id, ProductSKU.is_active.is_(True))
        )
        if not sku or not sku.product or not sku.product.is_active:
            raise not_found("sku not found")
        sku = await _resolve_role_sku(db, sku, expected_sku_type)
        if effective_role == UserRole.RETAIL and not sku.product.supports_retail:
            raise bad_request("product is not available for retail")
        if effective_role == UserRole.WHOLESALE and not sku.product.supports_wholesale:
            raise bad_request("product is not available for wholesale")
        min_qty = sku.min_wholesale_qty if effective_role == UserRole.WHOLESALE else sku.min_sale_qty
        if item.quantity < min_qty:
            raise bad_request(f"quantity for sku {sku.sku_code} must be at least {min_qty}")
        unit_price = sku.wholesale_price if effective_role == UserRole.WHOLESALE else sku.retail_price
        line_amount = unit_price * item.quantity
        original_amount += line_amount
        line_items.append((sku, item.quantity, unit_price))

    shipping_channel = "pickup" if payload.shipping_channel == "pickup" else "delivery"
    shipping_mode = ShippingMode.OFFLINE if shipping_channel == "pickup" else None
    shipping_fee = calculate_shipping_fee(
        role=effective_role,
        merchandise_amount=original_amount,
        shipping_channel=shipping_channel,
    )
    payable_amount = original_amount + shipping_fee
    if effective_role == UserRole.WHOLESALE and payload.payment_method == PaymentMethod.OFFLINE_TRANSFER:
        payable_amount = original_amount

    order = Order(
        order_no=generate_order_no(),
        customer_id=current_user.id,
        buyer_role=effective_role,
        status=OrderStatus.PENDING_PAYMENT,
        original_amount=original_amount,
        shipping_fee=shipping_fee,
        payable_amount=payable_amount,
        payment_method=payload.payment_method,
        shipping_mode=shipping_mode,
        shipping_recipient=payload.shipping_recipient,
        shipping_phone=payload.shipping_phone,
        shipping_province=payload.shipping_province,
        shipping_city=payload.shipping_city,
        shipping_district=payload.shipping_district,
        shipping_address=payload.shipping_address,
        note=payload.note,
        customer_note=payload.note,
    )
    db.add(order)
    await db.flush()

    for sku, quantity, unit_price in line_items:
        await change_online_stock(
            db=db,
            sku_id=sku.id,
            delta_qty=-quantity,
            reason=StockChangeReason.ORDER_CREATE,
            operator=current_user,
            ref_order_no=order.order_no,
            note="customer order create",
        )
        db.add(
            OrderItem(
                order_id=order.id,
                sku_id=sku.id,
                product_name_snapshot=sku.product.name,
                sku_code_snapshot=sku.sku_code,
                sku_type_snapshot=sku.sku_type.value,
                spec_value_1_snapshot=sku.spec_value_1,
                spec_value_2_snapshot=sku.spec_value_2,
                quantity=quantity,
                unit_price=unit_price,
                line_amount=unit_price * quantity,
            )
        )

    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.created",
        action_label="订单创建",
        source="customer",
        actor=current_user,
        after_data={
            "status": order.status.value,
            "buyer_role": order.buyer_role.value,
            "payment_method": order.payment_method.value,
            "original_amount": f"{order.original_amount:.2f}",
            "shipping_fee": f"{order.shipping_fee:.2f}",
            "payable_amount": f"{order.payable_amount:.2f}",
            "shipping_mode": order.shipping_mode.value if order.shipping_mode else None,
            "item_count": len(line_items),
        },
        evidence={
            "shipping_recipient": order.shipping_recipient,
            "shipping_phone": order.shipping_phone,
            "shipping_address": order.shipping_address,
        },
        note=order.customer_note,
        visibility="internal",
    )
    await notify_order_customer(
        db,
        order=order,
        title="订单已提交",
        summary=f"订单 {order.order_no} 已提交，正在等待付款。",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
        push_event_key="order_created",
        push_payload={
            "title": f"订单 {order.order_no}",
            "time": order.created_at.isoformat() if order.created_at else datetime.now(UTC).isoformat(),
            "status": "待支付",
            "amount": f"{order.payable_amount:.2f}",
            "note": "请尽快完成付款。",
        },
    )
    return order


async def cancel_order(
    db: AsyncSession,
    order: Order,
    operator: User | None = None,
    note: str | None = None,
    cancellation_source: str | None = None,
) -> Order:
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("only pending_payment orders can be canceled")
    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    for item in items:
        await change_online_stock(
            db=db,
            sku_id=item.sku_id,
            delta_qty=item.quantity,
            reason=StockChangeReason.ORDER_CANCEL,
            operator=operator,
            ref_order_no=order.order_no,
            note=note or "order canceled",
        )
    order.status = OrderStatus.CANCELED
    order.canceled_at = datetime.now(UTC)
    source = cancellation_source or (
        "auto_timeout"
        if operator is None
        else ("customer" if operator.role in {UserRole.RETAIL, UserRole.WHOLESALE} else "staff")
    )
    order.cancellation_source = source[:32]
    order.cancellation_reason = (note or ("超过支付时限，订单已自动取消" if source == "auto_timeout" else "订单已取消"))[:255]
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.canceled",
        action_label="订单取消",
        source="admin" if operator else "system",
        actor=operator,
        before_data={"status": OrderStatus.PENDING_PAYMENT.value},
        after_data={
            "status": order.status.value,
            "canceled_at": order.canceled_at.isoformat(),
            "cancellation_source": order.cancellation_source,
            "cancellation_reason": order.cancellation_reason,
        },
        evidence={"note": note} if note else {},
        note=note,
    )
    await notify_order_customer(
        db,
        order=order,
        title="订单已取消",
        summary=f"订单 {order.order_no} 已取消。",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
    )
    return order


async def terminate_order(
    db: AsyncSession,
    order: Order,
    *,
    operator: User,
    reason: str,
    disposition: str | None = None,
    internal_note: str | None = None,
) -> Order:
    if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.DELETED}:
        raise bad_request("only active orders can be terminated")

    before_status = order.status
    restored_stock = False
    if order.status == OrderStatus.PENDING_PAYMENT:
        items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
        for item in items:
            await change_online_stock(
                db=db,
                sku_id=item.sku_id,
                delta_qty=item.quantity,
                reason=StockChangeReason.ORDER_CANCEL,
                operator=operator,
                ref_order_no=order.order_no,
                note=reason,
            )
        restored_stock = True

    now = datetime.now(UTC)
    order.status = OrderStatus.CANCELED
    order.canceled_at = now
    order.terminated_at = now
    order.terminated_by_user_id = operator.id
    order.termination_reason = reason.strip()
    order.termination_disposition = (disposition or "").strip() or None
    if internal_note is not None:
        order.internal_note = internal_note.strip() or None
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.terminated",
        action_label="订单终止",
        source="admin" if operator.role == UserRole.ADMIN else "employee",
        actor=operator,
        before_data={"status": before_status.value},
        after_data={
            "status": order.status.value,
            "terminated_at": order.terminated_at.isoformat(),
            "reason": order.termination_reason,
            "disposition": order.termination_disposition,
            "stock_restored": restored_stock,
        },
        note=order.termination_reason,
    )
    await notify_order_customer(
        db,
        order=order,
        title="订单已终止",
        summary=f"订单 {order.order_no} 已终止：{order.termination_reason}",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
    )
    return order


async def delete_order(
    db: AsyncSession,
    order: Order,
    operator: User | None = None,
    note: str | None = None,
) -> Order:
    if order.status not in {OrderStatus.COMPLETED, OrderStatus.CANCELED}:
        raise bad_request("only completed or canceled orders can be deleted")
    before_status = order.status
    order.status = OrderStatus.DELETED
    order.deleted_at = datetime.now(UTC)
    order.deleted_by_user_id = operator.id if operator else None
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.deleted",
        action_label="订单删除",
        source="customer" if operator and operator.role in {UserRole.RETAIL, UserRole.WHOLESALE} else "admin",
        actor=operator,
        before_data={"status": before_status.value},
        after_data={
            "status": order.status.value,
            "deleted_at": order.deleted_at.isoformat() if order.deleted_at else None,
            "deleted_by_user_id": order.deleted_by_user_id,
        },
        note=note,
    )
    return order


async def mark_order_paid(
    db: AsyncSession,
    order: Order,
    operator: User | None = None,
    source: str = "system",
    note: str | None = None,
) -> Order:
    if order.status != OrderStatus.PENDING_PAYMENT:
        return order
    before_status = order.status
    order.status = OrderStatus.AWAITING_SHIPMENT
    order.paid_at = datetime.now(UTC)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="payment.confirmed",
        action_label="确认收款",
        source=source,
        actor=operator,
        before_data={"status": before_status.value},
        after_data={"status": order.status.value, "paid_at": order.paid_at.isoformat()},
        note=note,
    )
    await notify_order_customer(
        db,
        order=order,
        title="付款成功",
        summary=f"订单 {order.order_no} 已确认收款，等待店内发货。",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
        push_event_key="order_created",
        push_payload={
            "title": f"订单 {order.order_no}",
            "time": order.paid_at.isoformat(),
            "status": "待发货",
            "amount": f"{order.payable_amount:.2f}",
            "note": "支付成功，等待发货。",
        },
    )
    return order


async def ship_order(
    db: AsyncSession,
    order: Order,
    shipping_mode,
    shipping_proof_url: str | None,
    logistics_company: str | None,
    fulfillment_channel: str | None,
    carrier_contact: str | None,
    tracking_no: str | None,
    note: str | None,
    shipping_evidence: dict[str, list[str]] | None = None,
    operator: User | None = None,
    source: str = "system",
) -> Order:
    if order.status != OrderStatus.AWAITING_SHIPMENT:
        raise bad_request("order must be awaiting_shipment before shipping")
    before_status = order.status
    order.status = OrderStatus.SHIPPED
    order.shipping_mode = shipping_mode
    normalized_evidence = {
        key: [url.strip() for url in urls if isinstance(url, str) and url.strip()]
        for key, urls in (shipping_evidence or {}).items()
        if key in {"handoff", "scene", "freight", "photos"} and isinstance(urls, list)
    }
    order.shipping_evidence = normalized_evidence
    legacy_proof = next((url for urls in normalized_evidence.values() for url in urls), None)
    order.shipping_proof_url = shipping_proof_url.strip() if isinstance(shipping_proof_url, str) and shipping_proof_url.strip() else legacy_proof
    order.logistics_company = logistics_company
    order.fulfillment_channel = fulfillment_channel.strip() if isinstance(fulfillment_channel, str) and fulfillment_channel.strip() else None
    order.carrier_contact = carrier_contact.strip() if isinstance(carrier_contact, str) and carrier_contact.strip() else None
    order.tracking_no = tracking_no
    if note:
        order.internal_note = note.strip()
    order.shipped_at = datetime.now(UTC)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.shipped",
        action_label="订单发货",
        source=source,
        actor=operator,
        before_data={"status": before_status.value},
        after_data={
            "status": order.status.value,
            "shipping_mode": order.shipping_mode.value if order.shipping_mode else None,
            "fulfillment_channel": order.fulfillment_channel,
            "carrier_contact": order.carrier_contact,
            "logistics_company": order.logistics_company,
            "tracking_no": order.tracking_no,
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        },
        evidence={"shipping_proof_url": order.shipping_proof_url, "shipping_evidence": order.shipping_evidence} if order.shipping_proof_url else {"shipping_evidence": order.shipping_evidence},
        note=note,
    )
    await notify_order_customer(
        db,
        order=order,
        title="订单已发货",
        summary=f"订单 {order.order_no} 已发货，您可以在消息中心查看更新。",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
        push_event_key="order_shipped",
        push_payload={
            "title": f"订单 {order.order_no}",
            "time": order.shipped_at.isoformat() if order.shipped_at else datetime.now(UTC).isoformat(),
            "status": "已发货",
            "note": logistics_company or tracking_no or "请留意物流进度。",
            "amount": f"{order.payable_amount:.2f}",
        },
    )
    await sync_wechat_shipping_upload(db=db, order=order, operator=operator, source=source)
    return order


async def complete_order(
    db: AsyncSession,
    order: Order,
    operator: User | None = None,
    source: str = "system",
) -> Order:
    if order.status != OrderStatus.SHIPPED:
        raise bad_request("only shipped order can be completed")
    before_status = order.status
    signed_at = order.delivery_signed_at or datetime.now(UTC)
    order.status = OrderStatus.COMPLETED
    order.delivery_signed_at = signed_at
    order.completed_at = datetime.now(UTC)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.completed",
        action_label="订单完结",
        source=source,
        actor=operator,
        before_data={"status": before_status.value},
        after_data={
            "status": order.status.value,
            "delivery_signed_at": order.delivery_signed_at.isoformat() if order.delivery_signed_at else None,
            "completed_at": order.completed_at.isoformat(),
        },
    )
    await notify_order_customer(
        db,
        order=order,
        title="订单已完成",
        summary=f"订单 {order.order_no} 已完成。",
        route=f"/pages/order/detail?id={order.id}",
        kind="order",
        push_event_key="order_completed",
        push_payload={
            "title": f"订单 {order.order_no}",
            "time": order.completed_at.isoformat() if order.completed_at else datetime.now(UTC).isoformat(),
            "status": "已完成",
            "note": "如有问题可在消息中心发起售后。",
        },
    )
    return order


async def release_order_reservations(db: AsyncSession, order: Order) -> None:
    items = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    for item in items:
        await change_online_stock(
            db=db,
            sku_id=item.sku_id,
            delta_qty=item.quantity,
            reason=StockChangeReason.ORDER_CANCEL,
            operator=None,
            ref_order_no=order.order_no,
            note="release order reservation",
        )
