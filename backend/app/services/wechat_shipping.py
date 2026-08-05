import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models.enums import ShippingMode
from app.models.order import Order, OrderItem
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.payment import PaymentRecord
from app.models.user import User
from app.services.storefront_config import load_storefront_config
from app.services.wechat_mini import fetch_access_token

logger = logging.getLogger(__name__)

# ponytail: this covers the carriers the store currently uses; add the official
# get_delivery_list lookup only when a new carrier is actually needed.
EXPRESS_COMPANY_CODES = {
    "顺丰": "SF",
    "顺丰速运": "SF",
    "申通": "STO",
    "圆通": "YTO",
    "中通": "ZTO",
    "韵达": "YUNDA",
    "极兔": "JTSD",
    "京东": "JD",
    "邮政": "EMS",
}


def _mask_contact(value: str) -> str:
    digits = re.sub(r"\s+", "", value)
    if len(digits) <= 4:
        return digits
    if len(digits) <= 7:
        return f"***{digits[-4:]}"
    return f"{digits[:3]}****{digits[-4:]}"


def _is_pickup(order: Order, shipping_mode: ShippingMode, store_address: str) -> bool:
    if shipping_mode != ShippingMode.OFFLINE:
        return False
    shipping_address = (order.shipping_address or "").strip()
    recipient = (order.shipping_recipient or "").strip()
    return (
        shipping_address.startswith("到店自提")
        or recipient == "到店自提"
        or (bool(store_address) and shipping_address == store_address)
    )


def _express_company_code(value: str | None) -> str:
    raw = value.strip() if isinstance(value, str) else ""
    return EXPRESS_COMPANY_CODES.get(raw, raw.upper())


def _fulfillment_channel(order: Order, shipping_mode: ShippingMode, store_address: str) -> str:
    channel = (order.fulfillment_channel or "").strip()
    if channel in {"courier", "linehaul", "local_delivery", "pickup"}:
        return channel
    if _is_pickup(order, shipping_mode, store_address):
        return "pickup"
    return "courier" if shipping_mode == ShippingMode.EXPRESS else "linehaul"


def _require_mini_config() -> tuple[str, str]:
    settings = get_settings()
    app_id = settings.WECHAT_MINI_APP_ID or settings.WECHAT_APP_ID
    app_secret = settings.WECHAT_MINI_APP_SECRET
    if not app_id or not app_secret:
        raise bad_request("wechat mini app config missing")
    return app_id, app_secret


async def _post_wechat_api(url_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_mini_config()
    access_token = await fetch_access_token()
    query = parse.urlencode({"access_token": access_token})
    url = f"https://api.weixin.qq.com{url_path}?{query}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _run() -> dict[str, Any]:
        req = request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8")
                return json.loads(text) if text else {}
        except HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                body_text = str(e)
            raise bad_request(f"wechat shipping upload http error {e.code}: {body_text}") from e

    result = await asyncio.to_thread(_run)
    if result.get("errcode"):
        raise bad_request(f"wechat shipping upload failed: {result.get('errmsg')}")
    return result


async def upload_miniapp_shipping_info(
    db: AsyncSession,
    order: Order,
    shipping_mode: ShippingMode,
    logistics_company: str | None,
    tracking_no: str | None,
    shipping_proof_url: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.WECHAT_PAY_MOCK:
        return {"skipped": True, "reason": "wechat pay mock enabled"}
    if order.payment_method != PaymentMethod.WECHAT_PAY:
        return {"skipped": True, "reason": "order was not paid through wechat pay"}
    if not settings.WECHAT_MCH_ID:
        raise bad_request("wechat merchant id is missing")

    store_info = load_storefront_config().get("store_info") or {}
    customer = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == order.customer_id)
    )
    if not customer:
        raise bad_request("wechat shipping customer is unavailable")

    payer_openid = customer.profile.wechat_openid if customer.profile else None
    if not payer_openid:
        payer_openid = await db.scalar(
            select(PaymentRecord.openid)
            .where(
                PaymentRecord.order_id == order.id,
                PaymentRecord.status == PaymentStatus.PAID,
            )
            .order_by(PaymentRecord.id.desc())
            .limit(1)
        )
    if not payer_openid:
        raise bad_request("wechat shipping payer openid is unavailable")

    order_items = (
        await db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.id.asc())
        )
    ).all()
    item_desc = "；".join(
        f"{item.product_name_snapshot}*{item.quantity}" for item in order_items
    )[:120] or order.order_no

    store_phone = str(store_info.get("phone", "")).strip()
    store_address = str(store_info.get("address", "")).strip()
    receiver_phone = (
        customer.profile.phone
        if customer.profile and customer.profile.phone
        else (order.shipping_phone or "")
    ).strip()
    consignor_phone = store_phone or (order.shipping_phone or receiver_phone)
    fulfillment_channel = _fulfillment_channel(order, shipping_mode, store_address)
    if fulfillment_channel == "linehaul":
        return {
            "manual": True,
            "reason": "non-standard intercity logistics must be entered manually in the miniapp shipping console",
        }
    logistics_type = {"courier": 1, "local_delivery": 2, "pickup": 4}[fulfillment_channel]
    shipping_item: dict[str, Any] = {
        "item_desc": item_desc,
    }
    if logistics_type == 1:
        express_company = _express_company_code(logistics_company)
        tracking_value = tracking_no.strip() if isinstance(tracking_no, str) else ""
        if not express_company:
            raise bad_request("wechat shipping requires an express company code")
        if not tracking_value:
            raise bad_request("wechat shipping requires a tracking number")
        shipping_item["express_company"] = express_company
        shipping_item["tracking_no"] = tracking_value
        if express_company == "SF":
            contact = _mask_contact(consignor_phone or receiver_phone)
            if not contact:
                raise bad_request("wechat shipping requires a contact for SF Express")
            shipping_item["contact"] = {"consignor_contact": contact}

    payload: dict[str, Any] = {
        "order_key": {
            "order_number_type": 1,
            "mchid": settings.WECHAT_MCH_ID or "",
            "out_trade_no": order.order_no,
        },
        "logistics_type": logistics_type,
        "delivery_mode": 1,
        "shipping_list": [shipping_item],
        "upload_time": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "payer": {"openid": payer_openid},
    }
    response = await _post_wechat_api("/wxa/sec/order/upload_shipping_info", payload)
    logger.info("wechat shipping upload success order=%s response=%s", order.order_no, response)
    return {"success": True, "response": response, "payload": payload}
