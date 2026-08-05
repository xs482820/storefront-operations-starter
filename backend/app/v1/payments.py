import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import OrderStatus, PaymentStatus, UserRole
from app.models.order import Order
from app.models.payment import PaymentRecord
from app.models.user import User
from app.schemas.payment import (
    PaymentCreateIn,
    PaymentCreateOut,
    PaymentRecordOut,
    PaymentRefundIn,
    PaymentRefundOut,
    PaymentStatusUpdateIn,
)
from app.services.orders import release_order_reservations
from app.services.wechat_pay import (
    build_jsapi_pay_params,
    create_refund_transaction,
    create_jsapi_transaction,
    create_native_transaction,
    decrypt_wechat_resource,
    verify_wechatpay_signature,
)

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()


def generate_payment_no() -> str:
    return f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def generate_refund_no() -> str:
    return f"RFD{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"


def _serialize_payment(payment: PaymentRecord, order_no: str) -> PaymentRecordOut:
    return PaymentRecordOut(
        payment_no=payment.payment_no,
        order_no=order_no,
        channel=payment.channel,
        status=payment.status,
        amount=f"{payment.amount:.2f}",
        openid=payment.openid,
        prepay_id=payment.prepay_id,
        provider_txn_no=payment.provider_txn_no,
        note=payment.note,
        created_at=payment.created_at.isoformat(),
    )


def _payment_status_from_trade_state(trade_state: str) -> PaymentStatus:
    state = (trade_state or "").upper()
    if state == "SUCCESS":
        return PaymentStatus.PAID
    if state in {"CLOSED", "REVOKED", "PAYERROR"}:
        return PaymentStatus.FAILED
    if state == "REFUND":
        return PaymentStatus.REFUNDED
    return PaymentStatus.PENDING


def _payment_status_from_refund_state(refund_state: str) -> PaymentStatus:
    state = (refund_state or "").upper()
    if state == "SUCCESS":
        return PaymentStatus.REFUNDED
    if state in {"ABNORMAL", "CLOSED"}:
        return PaymentStatus.FAILED
    return PaymentStatus.PENDING


@router.post("/wechat/jsapi", response_model=PaymentCreateOut)
async def create_wechat_jsapi_payment(
    payload: PaymentCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaymentCreateOut:
    order = await db.scalar(select(Order).where(Order.order_no == payload.order_no))
    if not order:
        raise not_found("order not found")
    if current_user.role != UserRole.ADMIN and order.customer_id != current_user.id:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order status is not pending_payment")

    # Reuse latest pending JSAPI payment for the same order to avoid
    # WeChat "INVALID_REQUEST: 请求重入参数不一致" on repeated create calls.
    existing = await db.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.channel == payload.channel,
            PaymentRecord.status == PaymentStatus.PENDING,
        )
        .order_by(PaymentRecord.id.desc())
    )
    if existing and existing.prepay_id:
        if payload.openid and existing.openid and payload.openid != existing.openid:
            raise bad_request("openid mismatch with existing prepay")
        jsapi_params = build_jsapi_pay_params(existing.prepay_id) if not settings.WECHAT_PAY_MOCK else None
        return PaymentCreateOut(
            payment_no=existing.payment_no,
            order_no=order.order_no,
            channel=existing.channel,
            status=existing.status,
            amount=f"{existing.amount:.2f}",
            prepay_id=existing.prepay_id,
            jsapi_params=jsapi_params,
            message="reuse existing jsapi prepay",
        )

    payment = PaymentRecord(
        payment_no=generate_payment_no(),
        order_id=order.id,
        channel=payload.channel,
        status=PaymentStatus.PENDING,
        amount=Decimal(order.payable_amount),
        openid=payload.openid,
        note=payload.note,
        provider_payload={"mode": "mock_jsapi" if settings.WECHAT_PAY_MOCK else "wechat_v3_jsapi"},
    )
    if settings.WECHAT_PAY_MOCK:
        payment.prepay_id = f"mock_prepay_{order.order_no}"
    else:
        if not payload.openid:
            raise bad_request("openid is required for jsapi")
        rsp = await create_jsapi_transaction(
            order_no=order.order_no,
            amount=Decimal(order.payable_amount),
            openid=payload.openid,
            description=payload.note or f"Order {order.order_no}",
        )
        if not rsp.prepay_id:
            raise bad_request("wechat jsapi create failed")
        payment.prepay_id = rsp.prepay_id
        payment.provider_payload = rsp.raw or {}
    db.add(payment)
    await db.commit()

    jsapi_params = build_jsapi_pay_params(payment.prepay_id) if (payment.prepay_id and not settings.WECHAT_PAY_MOCK) else None
    return PaymentCreateOut(
        payment_no=payment.payment_no,
        order_no=order.order_no,
        channel=payload.channel,
        status=payment.status,
        amount=f"{payment.amount:.2f}",
        prepay_id=payment.prepay_id,
        jsapi_params=jsapi_params,
        message="mock jsapi prepay created" if settings.WECHAT_PAY_MOCK else "wechat jsapi prepay created",
    )


@router.post("/wechat/native", response_model=PaymentCreateOut)
async def create_wechat_native_payment(
    payload: PaymentCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaymentCreateOut:
    order = await db.scalar(select(Order).where(Order.order_no == payload.order_no))
    if not order:
        raise not_found("order not found")
    if current_user.role != UserRole.ADMIN and order.customer_id != current_user.id:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order status is not pending_payment")

    payment = PaymentRecord(
        payment_no=generate_payment_no(),
        order_id=order.id,
        channel="wechat_native",
        status=PaymentStatus.PENDING,
        amount=Decimal(order.payable_amount),
        note=payload.note,
        provider_payload={"mode": "mock_native" if settings.WECHAT_PAY_MOCK else "wechat_v3_native"},
    )
    code_url = None
    if settings.WECHAT_PAY_MOCK:
        code_url = f"weixin://wxpay/mock/{order.order_no}"
    else:
        rsp = await create_native_transaction(
            order_no=order.order_no,
            amount=Decimal(order.payable_amount),
            description=payload.note or f"Order {order.order_no}",
        )
        code_url = rsp.code_url
        payment.provider_payload = rsp.raw or {}
        if not code_url:
            raise bad_request("wechat native create failed")

    db.add(payment)
    await db.commit()
    return PaymentCreateOut(
        payment_no=payment.payment_no,
        order_no=order.order_no,
        channel=payment.channel,
        status=payment.status,
        amount=f"{payment.amount:.2f}",
        code_url=code_url,
        message="mock native code url created" if settings.WECHAT_PAY_MOCK else "wechat native code url created",
    )


@router.get("", response_model=list[PaymentRecordOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PaymentRecordOut]:
    rows = (
        await db.execute(
            select(PaymentRecord, Order.order_no)
            .join(Order, Order.id == PaymentRecord.order_id)
            .order_by(desc(PaymentRecord.id))
            .limit(100)
        )
    ).all()
    return [_serialize_payment(payment, order_no) for payment, order_no in rows]


@router.patch("/{payment_no}/status", response_model=PaymentRecordOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_payment_status(
    payment_no: str,
    payload: PaymentStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentRecordOut:
    payment = await db.scalar(select(PaymentRecord).where(PaymentRecord.payment_no == payment_no))
    if not payment:
        raise not_found("payment not found")
    order = await db.get(Order, payment.order_id)
    if not order:
        raise not_found("order not found")

    payment.status = payload.status
    payment.provider_txn_no = payload.provider_txn_no
    payment.note = payload.note or payment.note

    if payload.status == PaymentStatus.PAID and order.status == OrderStatus.PENDING_PAYMENT:
        order.status = OrderStatus.AWAITING_SHIPMENT
    if payload.status == PaymentStatus.REFUNDED and order.status != OrderStatus.CANCELED:
        await release_order_reservations(db=db, order=order)
        order.status = OrderStatus.CANCELED
    if payload.status == PaymentStatus.FAILED and order.status == OrderStatus.PENDING_PAYMENT:
        await release_order_reservations(db=db, order=order)
        order.status = OrderStatus.CANCELED

    await db.commit()
    return _serialize_payment(payment, order.order_no)


@router.post(
    "/wechat/refund",
    response_model=PaymentRefundOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def create_wechat_refund(
    payload: PaymentRefundIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentRefundOut:
    order = await db.scalar(select(Order).where(Order.order_no == payload.order_no))
    if not order:
        raise not_found("order not found")
    if order.status not in {OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED, OrderStatus.COMPLETED}:
        raise bad_request("order status does not support refund")

    payment = await db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == order.id, PaymentRecord.status == PaymentStatus.PAID)
        .order_by(PaymentRecord.id.desc())
    )
    if not payment:
        payment = await db.scalar(
            select(PaymentRecord)
            .where(PaymentRecord.order_id == order.id)
            .order_by(PaymentRecord.id.desc())
        )
    if not payment:
        raise not_found("payment not found")
    if payment.status == PaymentStatus.REFUNDED:
        raise bad_request("payment already refunded")
    if not settings.WECHAT_PAY_MOCK and payment.status != PaymentStatus.PAID:
        raise bad_request("only paid payment can be refunded")

    refund_amount = Decimal(payload.refund_amount) if payload.refund_amount is not None else Decimal(payment.amount)
    if refund_amount <= 0:
        raise bad_request("refund_amount must be greater than 0")
    if refund_amount > Decimal(payment.amount):
        raise bad_request("refund_amount cannot exceed payment amount")

    refund_no = generate_refund_no()
    if settings.WECHAT_PAY_MOCK:
        payment.status = PaymentStatus.REFUNDED
        payment.note = payload.reason or payment.note
        payment.provider_payload = {
            **(payment.provider_payload or {}),
            "mock_refund": {
                "out_refund_no": refund_no,
                "refund_amount": f"{refund_amount:.2f}",
                "status": "SUCCESS",
            },
        }
        if order.status != OrderStatus.CANCELED:
            await release_order_reservations(db=db, order=order)
            order.status = OrderStatus.CANCELED
        await db.commit()
        return PaymentRefundOut(
            order_no=order.order_no,
            payment_no=payment.payment_no,
            status=payment.status,
            refund_no=refund_no,
            refund_amount=f"{refund_amount:.2f}",
            message="mock refund success",
        )

    rsp = await create_refund_transaction(
        out_trade_no=order.order_no,
        out_refund_no=refund_no,
        total_amount=Decimal(payment.amount),
        refund_amount=refund_amount,
        reason=payload.reason,
    )
    payment.note = payload.reason or payment.note
    payment.provider_payload = {
        **(payment.provider_payload or {}),
        "refund_request": rsp,
        "refund_no": refund_no,
        "refund_amount": f"{refund_amount:.2f}",
    }
    await db.commit()
    return PaymentRefundOut(
        order_no=order.order_no,
        payment_no=payment.payment_no,
        status=payment.status,
        refund_no=refund_no,
        refund_amount=f"{refund_amount:.2f}",
        message="refund request accepted",
    )


@router.post("/wechat/callback/v2")
async def wechat_v2_callback(_: Request) -> dict:
    return {"status": "received", "version": "v2", "message": "mock callback placeholder"}


@router.post("/wechat/callback/v3")
async def wechat_v3_callback(req: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    body_text = (await req.body()).decode("utf-8")
    if settings.WECHAT_PAY_MOCK:
        return {"status": "received", "version": "v3", "message": "mock callback placeholder"}

    try:
        verify_wechatpay_signature(dict(req.headers), body_text)
    except Exception:
        raise bad_request("invalid wechatpay signature")

    body = json.loads(body_text or "{}")
    decrypted = decrypt_wechat_resource(body)

    out_trade_no = decrypted.get("out_trade_no")
    trade_state = (decrypted.get("trade_state") or "").upper()
    refund_state = (decrypted.get("refund_status") or "").upper()
    txn_id = decrypted.get("transaction_id")
    refund_id = decrypted.get("refund_id") or decrypted.get("out_refund_no")
    if not out_trade_no:
        raise bad_request("out_trade_no missing")

    order = await db.scalar(select(Order).where(Order.order_no == out_trade_no))
    if not order:
        raise not_found("order not found")
    payment = await db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == order.id, PaymentRecord.status == PaymentStatus.PENDING)
        .order_by(PaymentRecord.id.desc())
    )
    if not payment:
        payment = await db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == order.id)
        .order_by(PaymentRecord.id.desc())
        )
    if not payment:
        raise not_found("payment not found")

    is_refund_callback = bool(refund_state)
    target_status = (
        _payment_status_from_refund_state(refund_state) if is_refund_callback else _payment_status_from_trade_state(trade_state)
    )
    provider_txn_no = refund_id if is_refund_callback else txn_id

    # Idempotent: repeated callback with same txn/status returns success directly.
    if payment.provider_txn_no == provider_txn_no and payment.status == target_status:
        return {"code": "SUCCESS", "message": "success"}

    # Prevent status downgrade by out-of-order callbacks.
    final_states = {PaymentStatus.PAID, PaymentStatus.REFUNDED}
    if payment.status in final_states and target_status not in final_states:
        return {"code": "SUCCESS", "message": "success"}

    payment.provider_txn_no = provider_txn_no
    payment.provider_payload = decrypted
    payment.status = target_status

    if is_refund_callback:
        if target_status == PaymentStatus.REFUNDED:
            if order.status != OrderStatus.CANCELED:
                await release_order_reservations(db=db, order=order)
            order.status = OrderStatus.CANCELED
    else:
        if target_status == PaymentStatus.PAID and order.status == OrderStatus.PENDING_PAYMENT:
            order.status = OrderStatus.AWAITING_SHIPMENT
        elif target_status == PaymentStatus.REFUNDED:
            if order.status != OrderStatus.CANCELED:
                await release_order_reservations(db=db, order=order)
            order.status = OrderStatus.CANCELED
        elif target_status == PaymentStatus.FAILED and order.status == OrderStatus.PENDING_PAYMENT:
            await release_order_reservations(db=db, order=order)
            order.status = OrderStatus.CANCELED

    await db.commit()
    return {"code": "SUCCESS", "message": "success"}
