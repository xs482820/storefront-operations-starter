from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from urllib import request
from urllib.error import HTTPError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models.user import User
from app.services.storefront_config import load_storefront_config
from app.services.wechat_mini import fetch_access_token

logger = logging.getLogger(__name__)


def _notification_channels_enabled() -> set[str]:
    settings = get_settings()
    return {item.strip() for item in settings.WECHAT_NOTIFICATION_CHANNELS.split(",") if item.strip()}


def _build_event_payload(event_config: dict, payload: dict[str, object]) -> dict[str, dict[str, str]]:
    field_keys = event_config.get("field_keys") if isinstance(event_config.get("field_keys"), dict) else {}
    data: dict[str, dict[str, str]] = {}

    def compact_text(value: object, limit: int = 20) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text[:limit]

    def template_prefix(template_key: str) -> str:
        match = re.match(r"([a-zA-Z_]+)", template_key.strip())
        return match.group(1).lower() if match else ""

    def number_text(value: object, *, allow_decimal: bool = True) -> str:
        text = re.sub(r"[^0-9.]", "", str(value or "").strip())
        if not allow_decimal:
            return re.sub(r"\D", "", text)[:20]
        if not text:
            return ""
        try:
            return f"{float(text):.2f}"
        except ValueError:
            return text[:20]

    def ascii_only(value: object, limit: int = 20) -> str:
        text = re.sub(r"[^0-9A-Za-z_-]", "", str(value or "").strip())
        return text[:limit]

    def format_time(value: object, *, date_only: bool = False) -> str:
        text = str(value or "").strip()
        if not text:
            now = datetime.now()
            return now.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M")
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M")
        except ValueError:
            if date_only:
                return text[:10]
            return text.replace("T", " ")[:16]

    def raw_value(semantic_key: str) -> object:
        fallbacks = {
            "title": "订单提醒",
            "order_no": payload.get("order_no") or payload.get("title") or "订单",
            "time": payload.get("time") or payload.get("apply_time") or payload.get("review_time"),
            "apply_time": payload.get("apply_time") or payload.get("time"),
            "review_time": payload.get("review_time") or payload.get("time"),
            "status": payload.get("status") or payload.get("result") or "处理中",
            "result": payload.get("result") or payload.get("status") or "审核完成",
            "product_name": payload.get("product_name") or "商品",
            "aftersale_type": payload.get("aftersale_type") or "售后",
            "merchant_name": payload.get("merchant_name") or "商家",
            "recipient": payload.get("recipient") or "收货人",
            "shipping_mode": payload.get("shipping_mode") or "配送",
            "phone": payload.get("phone") or payload.get("contact_phone"),
            "amount": payload.get("amount") or payload.get("refund_amount") or payload.get("payable_amount"),
            "note": payload.get("note") or payload.get("product_name") or "请查看详情",
        }
        return payload.get(semantic_key) or fallbacks.get(semantic_key) or ""

    def sanitize_value(template_key: str, semantic_key: str, value: object) -> str:
        prefix = template_prefix(template_key)
        if prefix == "thing":
            if semantic_key == "title":
                return "订单提醒"
            if semantic_key == "order_no":
                return "关联订单"
            if semantic_key == "phone":
                return "已绑定手机"
            return compact_text(value, 20)
        if prefix == "phrase":
            return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", compact_text(value, 8))[:5] or "处理中"
        if prefix == "time":
            return format_time(value)
        if prefix == "date":
            return format_time(value, date_only=True)
        if prefix == "amount":
            return f"{number_text(value) or '0.00'}元"
        if prefix in {"number", "integer", "digit"}:
            return number_text(value, allow_decimal=prefix not in {"integer", "digit"}) or "0"
        if prefix in {"character_string", "characterstring"}:
            return ascii_only(value, 32) or "YYORDER"
        if prefix in {"phone_number", "phone"}:
            return number_text(value, allow_decimal=False)[:20] or "13800000000"
        return compact_text(value, 20)

    for semantic_key, template_key in field_keys.items():
        template_key = str(template_key or "").strip()
        if not template_key:
            continue
        text = sanitize_value(template_key, str(semantic_key), raw_value(str(semantic_key)))
        if not text:
            continue
        data[template_key] = {"value": text}
    return data


async def send_miniapp_subscription_message(
    db: AsyncSession,
    *,
    user_id: int,
    event_key: str,
    payload: dict[str, object],
) -> bool:
    if "miniapp_subscribe" not in _notification_channels_enabled():
        return False

    storefront_config = load_storefront_config()
    notification_settings = storefront_config.get("notification_settings") or {}
    if not notification_settings.get("enabled"):
        return False

    miniapp_settings = notification_settings.get("miniapp_subscribe") or {}
    if not miniapp_settings.get("enabled"):
        return False

    events = miniapp_settings.get("events") or []
    event_config = next(
        (
            item
            for item in events
            if isinstance(item, dict) and item.get("key") == event_key
        ),
        None,
    )
    if not event_config or not event_config.get("enabled") or not event_config.get("template_id"):
        return False

    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
    )
    if not user or not user.profile or not user.profile.wechat_openid:
        return False
    if not user.profile.miniapp_notification_enabled:
        return False
    if event_key not in set(user.profile.miniapp_notification_event_keys or []):
        return False

    data = _build_event_payload(event_config, payload)
    if not data:
        return False

    access_token = await fetch_access_token()
    body = {
        "touser": user.profile.wechat_openid,
        "template_id": str(event_config.get("template_id", "")).strip(),
        "page": str(event_config.get("page", "")).strip().lstrip("/") or "pages/my/my",
        "miniprogram_state": "formal",
        "lang": "zh_CN",
        "data": data,
    }
    url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}"
    payload_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def _run() -> dict:
        req = request.Request(
            url=url,
            data=payload_bytes,
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
        except HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8")
            except Exception:
                body_text = str(exc)
            raise bad_request(f"wechat subscribe http error {exc.code}: {body_text}") from exc

    try:
        result = await asyncio.to_thread(_run)
        if result.get("errcode") not in (None, 0):
            logger.warning(
                "miniapp subscribe send failed: user_id=%s event_key=%s template_id=%s data_keys=%s errcode=%s errmsg=%s",
                user_id,
                event_key,
                str(event_config.get("template_id", "")).strip(),
                sorted(data.keys()),
                result.get("errcode"),
                result.get("errmsg"),
            )
            return False
        return True
    except Exception as exc:  # best effort only
        logger.warning(
            "miniapp subscribe send error: user_id=%s event_key=%s error=%s",
            user_id,
            event_key,
            exc,
        )
        return False
