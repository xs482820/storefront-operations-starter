from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.aftersale import AfterSaleRequest
from app.models.enums import AfterSaleProcessType, AfterSaleStatus, OrderStatus, PaymentMethod, PaymentStatus, UserRole
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.user import User
from app.schemas.employee import (
    EmployeeCancelOrderIn,
    EmployeeConfirmOfflinePaymentIn,
    EmployeeOrderNoteIn,
    EmployeeResolveAfterSaleIn,
    EmployeeSetDeliverySignedIn,
    EmployeeShipOrderIn,
)
from app.services.events import write_business_event
from app.services.notifications import create_customer_notification
from app.services.orders import cancel_order, complete_order, mark_order_paid, ship_order

router = APIRouter(prefix="/employee", tags=["employee"])


def _amount_to_str(value: Decimal | int | float | None) -> str:
    return f"{Decimal(value or 0):.2f}"


@router.get("/orders", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: OrderStatus | None = Query(default=None),
) -> list[dict]:
    stmt = select(Order).order_by(desc(Order.id)).limit(300)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    rows = (await db.scalars(stmt)).all()
    order_ids = [row.id for row in rows]
    customer_ids = [row.customer_id for row in rows if row.customer_id]

    users = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(customer_ids))
        )
    ).all() if customer_ids else []
    user_map = {user.id: user for user in users}

    items = (
        await db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id.in_(order_ids))
            .order_by(OrderItem.id.asc())
        )
    ).all() if order_ids else []
    items_by_order: dict[int, list[OrderItem]] = {}
    for item in items:
        items_by_order.setdefault(item.order_id, []).append(item)

    result: list[dict] = []
    for row in rows:
        user = user_map.get(row.customer_id)
        order_items = items_by_order.get(row.id, [])
        result.append(
            {
                "id": row.id,
                "order_no": row.order_no,
                "status": row.status.value,
                "buyer_role": row.buyer_role.value,
                "payment_method": row.payment_method.value,
                "shipping_mode": row.shipping_mode.value if row.shipping_mode else None,
                "shipping_recipient": row.shipping_recipient,
                "shipping_phone": row.shipping_phone,
                "shipping_address": row.shipping_address,
                "shipping_proof_url": row.shipping_proof_url,
                "logistics_company": row.logistics_company,
                "tracking_no": row.tracking_no,
                "note": row.note,
                "created_at": row.created_at.isoformat(),
                "paid_at": row.paid_at.isoformat() if row.paid_at else None,
                "shipped_at": row.shipped_at.isoformat() if row.shipped_at else None,
                "delivery_signed_at": row.delivery_signed_at.isoformat() if row.delivery_signed_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "canceled_at": row.canceled_at.isoformat() if row.canceled_at else None,
                "original_amount": _amount_to_str(row.original_amount),
                "shipping_fee": _amount_to_str(row.shipping_fee),
                "payable_amount": _amount_to_str(row.payable_amount),
                "customer_name": (
                    user.profile.display_name
                    if user and user.profile and user.profile.display_name
                    else (user.username if user else "unknown")
                ),
                "customer_phone": user.profile.phone if user and user.profile else None,
                "item_count": len(order_items),
                "item_summary": order_items[0].product_name_snapshot if order_items else None,
                "lines": [
                    {
                        "sku_id": item.sku_id,
                        "product_name": item.product_name_snapshot,
                        "sku_code": item.sku_code_snapshot,
                        "spec_value_1": item.spec_value_1_snapshot,
                        "spec_value_2": item.spec_value_2_snapshot,
                        "quantity": item.quantity,
                        "unit_price": _amount_to_str(item.unit_price),
                        "line_amount": _amount_to_str(item.line_amount),
                    }
                    for item in order_items
                ],
            }
        )
    return result


@router.post(
    "/orders/{order_id}/confirm-offline-payment",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def confirm_offline_payment(
    order_id: int,
    payload: EmployeeConfirmOfflinePaymentIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.payment_method != PaymentMethod.OFFLINE_TRANSFER:
        raise bad_request("order is not offline_transfer")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order is not pending_payment")

    payment = PaymentRecord(
        payment_no=f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
        order_id=order.id,
        channel="offline_transfer",
        status=PaymentStatus.PAID,
        amount=Decimal(order.original_amount),
        note=payload.note,
        provider_payload={"confirmed_by_employee": True},
    )
    db.add(payment)
    await db.flush()
    await mark_order_paid(db=db, order=order, operator=current_user, source="employee", note=payload.note)
    await write_business_event(
        db=db,
        entity_type="payment",
        entity_id=payment.id,
        entity_no=payment.payment_no,
        action_code="payment.confirmed",
        action_label="线下收款确认",
        source="employee",
        actor=current_user,
        after_data={
            "status": payment.status.value,
            "amount": f"{payment.amount:.2f}",
            "channel": payment.channel,
            "provider_txn_no": payment.provider_txn_no,
        },
        note=payload.note,
    )
    await db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "status": order.status.value}


@router.post(
    "/orders/{order_id}/ship",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def employee_ship_order(
    order_id: int,
    payload: EmployeeShipOrderIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    order = await ship_order(
        db=db,
        order=order,
        shipping_mode=payload.shipping_mode,
        shipping_proof_url=payload.shipping_proof_url,
        logistics_company=payload.logistics_company,
        tracking_no=payload.tracking_no,
        note=payload.note,
        operator=current_user,
        source="employee",
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "shipping_mode": order.shipping_mode.value if order.shipping_mode else None,
    }


@router.post(
    "/orders/{order_id}/note",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def save_order_followup_note(
    order_id: int,
    payload: EmployeeOrderNoteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("only pending_payment order can save follow-up note")
    order.note = (payload.note or "").strip() or None
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.note.updated",
        action_label="订单备注更新",
        source="employee",
        actor=current_user,
        after_data={"note": order.note},
        note=order.note,
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "note": order.note,
    }


@router.post(
    "/orders/{order_id}/mark-delivered",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def mark_delivered(
    order_id: int,
    payload: EmployeeSetDeliverySignedIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.SHIPPED:
        raise bad_request("only shipped order can be marked delivered")
    order.delivery_signed_at = payload.signed_at
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.signed",
        action_label="客户签收",
        source="employee",
        actor=current_user,
        after_data={"delivery_signed_at": order.delivery_signed_at.isoformat()},
    )
    await complete_order(db=db, order=order, operator=current_user, source="employee")
    await db.commit()
    return {
        "order_id": order.id,
        "delivery_signed_at": order.delivery_signed_at.isoformat(),
        "status": order.status.value,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }


@router.post(
    "/orders/{order_id}/cancel",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def cancel_pending_order(
    order_id: int,
    payload: EmployeeCancelOrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    order = await cancel_order(
        db=db,
        order=order,
        operator=current_user,
        note=payload.note or "employee canceled pending order",
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
    }


@router.get("/aftersales", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_aftersales(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: AfterSaleStatus | None = Query(default=None),
) -> list[dict]:
    stmt = (
        select(AfterSaleRequest)
        .order_by(desc(AfterSaleRequest.id))
        .limit(200)
    )
    if status is not None:
        stmt = stmt.where(AfterSaleRequest.status == status)
    rows = (await db.scalars(stmt)).all()
    order_ids = [row.order_id for row in rows]
    customer_ids = [row.customer_id for row in rows if row.customer_id]
    handler_ids = [row.handler_employee_id for row in rows if row.handler_employee_id]

    orders = (
        await db.scalars(select(Order).where(Order.id.in_(order_ids)))
    ).all() if order_ids else []
    order_map = {order.id: order for order in orders}

    users = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(customer_ids + handler_ids))
        )
    ).all() if customer_ids or handler_ids else []
    user_map = {user.id: user for user in users}

    result: list[dict] = []
    for row in rows:
        order = order_map.get(row.order_id)
        customer = user_map.get(row.customer_id)
        handler = user_map.get(row.handler_employee_id)
        result.append(
            {
                "id": row.id,
                "order_id": row.order_id,
                "order_no": order.order_no if order else None,
                "buyer_role": order.buyer_role.value if order else None,
                "customer_name": (
                    customer.profile.display_name
                    if customer and customer.profile and customer.profile.display_name
                    else (customer.username if customer else "unknown")
                ),
                "customer_phone": customer.profile.phone if customer and customer.profile else None,
                "reason": row.reason.value,
                "custom_reason_text": row.custom_reason_text,
                "process_type": row.process_type.value if row.process_type else None,
                "refund_amount": _amount_to_str(row.refund_amount) if row.refund_amount is not None else None,
                "chat_proof_url": row.chat_proof_url,
                "status": row.status.value,
                "note": row.note,
                "handler_employee_id": row.handler_employee_id,
                "handler_name": (
                    handler.profile.display_name
                    if handler and handler.profile and handler.profile.display_name
                    else (handler.username if handler else None)
                ),
                "created_at": row.created_at.isoformat(),
            }
        )
    return result


@router.post(
    "/aftersales/{aftersale_id}/resolve",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def resolve_aftersale(
    aftersale_id: int,
    payload: EmployeeResolveAfterSaleIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.get(AfterSaleRequest, aftersale_id)
    if not row:
        raise not_found("aftersale not found")
    order = await db.get(Order, row.order_id)
    if not order:
        raise not_found("order not found")

    before_status = row.status
    row.process_type = payload.process_type
    row.refund_amount = payload.refund_amount
    row.chat_proof_url = payload.chat_proof_url
    row.note = payload.note
    row.handler_employee_id = current_user.id
    row.status = AfterSaleStatus.RESOLVED
    await write_business_event(
        db=db,
        entity_type="aftersale",
        entity_id=row.id,
        entity_no=row.request_no,
        action_code="aftersale.resolved",
        action_label="售后完结",
        source="employee",
        actor=current_user,
        before_data={"status": before_status.value},
        after_data={
            "status": row.status.value,
            "process_type": row.process_type.value if row.process_type else None,
            "refund_amount": f"{Decimal(row.refund_amount):.2f}" if row.refund_amount is not None else None,
            "handler_employee_id": row.handler_employee_id,
        },
        evidence={"chat_proof_url": row.chat_proof_url} if row.chat_proof_url else {},
        note=row.note,
    )
    order.status = OrderStatus.CANCELED if payload.process_type != AfterSaleProcessType.EXCHANGE else order.status
    if order.status == OrderStatus.CANCELED:
        order.canceled_at = datetime.now(UTC)
        await write_business_event(
            db=db,
            entity_type="order",
            entity_id=order.id,
            entity_no=order.order_no,
            action_code="order.canceled",
            action_label="订单取消",
            source="employee",
            actor=current_user,
            after_data={"status": order.status.value, "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None},
            note=payload.note,
        )
    if row.customer_id:
        await create_customer_notification(
            db,
            user_id=row.customer_id,
            title="售后已处理",
            summary=f"售后单 {row.request_no} 已处理完成。",
            kind="aftersale",
            route="/pages/aftersale/list",
            push_event_key="aftersale_resolved",
            push_payload={
                "title": f"售后单 {row.request_no}",
                "time": datetime.now(UTC).isoformat(),
                "status": "已处理",
                "amount": f"{Decimal(row.refund_amount):.2f}" if row.refund_amount is not None else "0.00",
                "note": row.note or "请查看处理结果。",
            },
        )
    await db.commit()
    return {"id": row.id, "status": row.status.value, "order_status": order.status.value}
