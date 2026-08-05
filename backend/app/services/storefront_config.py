from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import json
from typing import Any

from app.core.config import get_settings

STOREFRONT_CONFIG_PATH = Path("/app/data/storefront-config.json")
PUBLIC_ASSET_BASE_URL = get_settings().PUBLIC_ASSET_BASE_URL.rstrip("/")


def _event(
    key: str,
    label: str,
    *,
    desc: str,
    page: str,
    field_keys: dict[str, str],
    field_mode: str = "editable",
    field_note: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "desc": desc,
        "enabled": enabled,
        "template_id": "",
        "page": page,
        "field_keys": field_keys,
        "field_mode": field_mode,
        "field_note": field_note,
    }


DEFAULT_NOTIFICATION_EVENTS: list[dict[str, Any]] = [
    _event(
        "order_created",
        "待付款提醒",
        desc="客户提交订单后等待付款提醒",
        page="/pages/order/list",
        field_mode="editable",
        field_note="适合待付款模板；关键词可按微信模板顺序填写。",
        field_keys={
            "note": "thing1",
            "order_no": "character_string4",
            "status": "phrase3",
            "amount": "amount5",
            "time": "time6",
        },
    ),
    _event(
        "order_shipped",
        "订单发货提醒",
        desc="订单出库完成后提醒",
        page="/pages/order/list",
        field_mode="fixed",
        field_note="模板内容通常已定义完整，建议保持默认映射。",
        field_keys={
            "order_no": "character_string1",
            "product_name": "thing21",
            "recipient": "thing14",
            "shipping_mode": "thing17",
            "time": "date3",
        },
    ),
    _event(
        "order_completed",
        "自动签收提醒",
        desc="订单自动签收或收尾完成后提醒",
        page="/pages/order/list",
        field_mode="fixed",
        field_note="模板内容通常已定义完整，建议保持默认映射。",
        field_keys={
            "order_no": "character_string2",
            "time": "date1",
            "review_time": "date3",
        },
    ),
    _event(
        "aftersale_created",
        "售后服务进度通知",
        desc="客户提交售后后，跟进处理进度提醒",
        page="/pages/aftersale/list",
        field_mode="fixed",
        field_note="模板内容通常已定义完整，建议保持默认映射。",
        field_keys={
            "order_no": "character_string7",
            "product_name": "thing3",
            "aftersale_type": "thing1",
            "status": "phrase2",
            "amount": "amount5",
        },
    ),
    _event(
        "wholesale_reviewed",
        "申请结果通知",
        desc="批发申请审核结果提醒",
        page="/pages/my/my",
        field_mode="fixed",
        field_note="模板内容通常已定义完整，建议保持默认映射。",
        field_keys={
            "result": "phrase2",
            "merchant_name": "thing4",
            "phone": "phone_number6",
            "apply_time": "time8",
            "review_time": "date1",
        },
    ),
]

DEFAULT_SHIPPING_RULES = {
    "retail": {"express": "8.00", "linehaul": "12.00", "pickup": "0.00"},
    "wholesale": {"express": "12.00", "linehaul": "18.00", "pickup": "0.00"},
}

DEFAULT_SHIPPING_THRESHOLDS = {
    "retail": "99.00",
    "wholesale": "199.00",
}

DEFAULT_SHIPPING_THRESHOLD_SWITCHES = {
    "retail": True,
    "wholesale": False,
}

DEFAULT_SHIPPING_POLICY = {
    "role_specific": False,
    "delivery_fee": "8.00",
    "free_shipping_threshold": "99.00",
    "retail": {"delivery_fee": "8.00", "free_shipping_threshold": "99.00"},
    "wholesale": {"delivery_fee": "8.00", "free_shipping_threshold": "99.00"},
}

SENSITIVE_AI_KEYS = {"api_key"}


def _settings() -> Any:
    return get_settings()


def default_ai_settings(*, include_secrets: bool = False) -> dict[str, Any]:
    settings = _settings()
    result: dict[str, Any] = {
        "enabled": bool(settings.AI_ADMIN_ENABLED),
        "dry_run": bool(settings.AI_ADMIN_DRY_RUN),
        "provider": "deepseek",
        "base_url": settings.DEEPSEEK_BASE_URL,
        "model": settings.DEEPSEEK_MODEL,
        "timeout_seconds": int(settings.DEEPSEEK_TIMEOUT_SECONDS),
        "max_output_tokens": int(settings.DEEPSEEK_MAX_OUTPUT_TOKENS),
        "api_key_set": bool(settings.DEEPSEEK_API_KEY),
    }
    if include_secrets:
        result["api_key"] = settings.DEEPSEEK_API_KEY or ""
    return result


def default_image_ai_settings(*, include_secrets: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "enabled": False,
        "provider": "openai_compatible",
        "base_url": "",
        "model": "",
        "timeout_seconds": 90,
        "max_input_images": 1,
        "api_key_set": False,
    }
    if include_secrets:
        result["api_key"] = ""
    return result


def default_system_settings() -> dict[str, Any]:
    settings = _settings()
    return {
        "app": {
            "app_env": settings.APP_ENV,
            "app_debug": bool(settings.APP_DEBUG),
            "public_asset_base_url": settings.PUBLIC_ASSET_BASE_URL,
        },
        "auth": {
            "auth_sms_mock": bool(settings.AUTH_SMS_MOCK),
            "auth_sms_code_ttl_seconds": int(settings.AUTH_SMS_CODE_TTL_SECONDS),
            "auth_sms_resend_seconds": int(settings.AUTH_SMS_RESEND_SECONDS),
        },
        "scheduler": {
            "enabled": bool(settings.SCHEDULER_ENABLED),
            "interval_seconds": int(settings.SCHEDULER_INTERVAL_SECONDS),
            "express_auto_complete_days": int(settings.SCHEDULER_EXPRESS_AUTO_COMPLETE_DAYS),
            "offline_auto_complete_days": int(settings.SCHEDULER_OFFLINE_AUTO_COMPLETE_DAYS),
        },
        "wechat": {
            "pay_mock": bool(settings.WECHAT_PAY_MOCK),
            "notification_channels": settings.WECHAT_NOTIFICATION_CHANNELS,
            "mini_app_id": settings.WECHAT_MINI_APP_ID or "",
            "app_id": settings.WECHAT_APP_ID or "",
            "mch_id": settings.WECHAT_MCH_ID or "",
            "notify_url": settings.WECHAT_NOTIFY_URL or "",
            "refund_notify_url": settings.WECHAT_REFUND_NOTIFY_URL or "",
        },
        "print": {
            "provider": settings.PRINT_PROVIDER,
            "job_ttl_seconds": int(settings.PRINT_JOB_TTL_SECONDS),
        },
        "sensitive_status": {
            "jwt_secret_key": settings.JWT_SECRET_KEY != "change-this-secret",
            "database_url": bool(settings.DATABASE_URL),
            "redis_url": bool(settings.REDIS_URL),
            "wechat_mini_app_secret": bool(settings.WECHAT_MINI_APP_SECRET),
            "wechat_api_v3_key": bool(settings.WECHAT_API_V3_KEY),
            "wechat_private_key_path": bool(settings.WECHAT_PRIVATE_KEY_PATH),
            "wechat_platform_cert_path": bool(settings.WECHAT_PLATFORM_CERT_PATH),
        },
    }


def default_notification_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "miniapp_subscribe": {
            "enabled": True,
            "events": deepcopy(DEFAULT_NOTIFICATION_EVENTS),
        },
    }


def default_storefront_config(*, include_secrets: bool = False) -> dict[str, Any]:
    return {
        "home_banners": [],
        "login_page": {
            "avatar_url": "",
        },
        "store_info": {
            "name": "",
            "phone": "",
            "address": "",
            "pickup_note": "",
        },
        "customer_service": {
            "wechat_id": "",
            "wechat_qr_url": "",
        },
        "shipping_thresholds": deepcopy(DEFAULT_SHIPPING_THRESHOLDS),
        "shipping_thresholds_enabled": deepcopy(DEFAULT_SHIPPING_THRESHOLD_SWITCHES),
        "shipping_rules": deepcopy(DEFAULT_SHIPPING_RULES),
        "shipping_policy": deepcopy(DEFAULT_SHIPPING_POLICY),
        "notification_settings": default_notification_settings(),
        "ai_settings": default_ai_settings(include_secrets=include_secrets),
        "image_ai_settings": default_image_ai_settings(include_secrets=include_secrets),
        "print_layout": (
            "==============================================\n"
            "                  示例门店\n"
            "                  发货配货单\n"
            "==============================================\n"
            "订单：{{order_no}}\n"
            "客户：{{recipient}}\n"
            "收货：{{shipping_channel}}\n"
            "----------------------------------------------\n"
            "商品明细\n"
            "  规格/属性              单价   数量    金额\n"
            "-----------------------------------------------\n"
            "{{lines}}\n"
            "-----------------------------------------------\n"
            "{{total_summary}}\n"
            "客户备注：{{customer_note}}\n"
            "店内备注：{{internal_note}}\n"
            "-----------------------------------------------\n"
            "签收前请核对商品数量与款式。\n"
            "售后问题请拍照联系客服：{{wechat_id}}\n"
            "电话联系：{{store_phone}}\n"
            "打印时间：{{printed_at}}"
        ),
        "system_settings": default_system_settings(),
        "watermark": {
            "enabled": True,
            "customer_enabled": True,
            "employee_enabled": False,
            "opacity": 0.05,
            "density": 5,
            "angle": 45,
        },
        "updated_at": None,
    }


def _normalize_image_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.startswith("blob:"):
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        if "/api/v1/admin/uploads/" in text or "/api/v1/customer/uploads/" in text:
            try:
                path = text.split("/api/v1/", 1)[1]
                return f"{PUBLIC_ASSET_BASE_URL}/api/v1/{path}"
            except Exception:
                return text[:500]
        return text[:500]
    return text[:500]


def _normalize_print_layout(value: Any, default: str) -> str:
    text = str(value if value is not None else "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return (text or default)[:5000]


def _normalize_banners(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    banners: list[dict[str, Any]] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        banners.append(
            {
                "title": str(item.get("title", "")).strip()[:40],
                "image_url": _normalize_image_url(item.get("image_url")),
                "link_type": str(item.get("link_type", "none")).strip()[:24] or "none",
                "link_value": str(item.get("link_value", "")).strip()[:500],
                "sort_order": int(item.get("sort_order", 0) or 0),
                "is_active": bool(item.get("is_active", True)),
            }
        )
    return banners


def _normalize_customer_service(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "wechat_id": str(source.get("wechat_id", "")).strip()[:64],
        "wechat_qr_url": _normalize_image_url(source.get("wechat_qr_url")),
    }


def _normalize_login_page(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "avatar_url": _normalize_image_url(source.get("avatar_url")),
    }


def _normalize_store_info(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "name": str(source.get("name", "")).strip()[:100],
        "phone": str(source.get("phone", "")).strip()[:32],
        "address": str(source.get("address", "")).strip()[:255],
        "pickup_note": str(source.get("pickup_note", "")).strip()[:255],
    }


def _normalize_shipping_rules(raw: Any) -> dict[str, dict[str, str]]:
    source = raw if isinstance(raw, dict) else {}
    sanitized: dict[str, dict[str, str]] = {}
    for role, defaults in DEFAULT_SHIPPING_RULES.items():
        role_source = source.get(role) if isinstance(source.get(role), dict) else {}
        sanitized[role] = {}
        for channel in ("express", "linehaul", "pickup"):
            try:
                value = Decimal(str(role_source.get(channel, defaults[channel])))
            except Exception:
                value = Decimal(defaults[channel])
            if value < 0:
                value = Decimal("0.00")
            sanitized[role][channel] = f"{value:.2f}"
    return sanitized


def _normalize_shipping_thresholds(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    sanitized: dict[str, str] = {}
    for role, default_value in DEFAULT_SHIPPING_THRESHOLDS.items():
        try:
            value = Decimal(str(source.get(role, default_value)))
        except Exception:
            value = Decimal(default_value)
        if value < 0:
            value = Decimal("0.00")
        sanitized[role] = f"{value:.2f}"
    return sanitized


def _normalize_shipping_policy(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, Any] = {"role_specific": _bool_value(source.get("role_specific"), False)}
    for key in ("delivery_fee", "free_shipping_threshold"):
        default = DEFAULT_SHIPPING_POLICY[key]
        try:
            value = Decimal(str(source.get(key, default)))
        except Exception:
            value = Decimal(default)
        result[key] = f"{max(value, Decimal('0.00')):.2f}"
    for role in ("retail", "wholesale"):
        role_source = source.get(role) if isinstance(source.get(role), dict) else {}
        result[role] = {}
        for key in ("delivery_fee", "free_shipping_threshold"):
            try:
                value = Decimal(str(role_source.get(key, result[key])))
            except Exception:
                value = Decimal(result[key])
            result[role][key] = f"{max(value, Decimal('0.00')):.2f}"
    return result


def _normalize_watermark(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    enabled = _bool_value(source.get("enabled"), True)
    try:
        opacity = float(source.get("opacity", 0.05) or 0.05)
    except (TypeError, ValueError):
        opacity = 0.05
    return {
        "enabled": enabled,
        "customer_enabled": _bool_value(source.get("customer_enabled"), enabled),
        "employee_enabled": _bool_value(source.get("employee_enabled"), False),
        "opacity": max(0.02, min(0.12, opacity)),
        "density": _int_value(source.get("density"), 5, minimum=1, maximum=10),
        "angle": _int_value(source.get("angle"), 45, minimum=15, maximum=45),
    }


def _normalize_shipping_threshold_switches(raw: Any) -> dict[str, bool]:
    source = raw if isinstance(raw, dict) else {}
    sanitized: dict[str, bool] = {}
    for role, default_value in DEFAULT_SHIPPING_THRESHOLD_SWITCHES.items():
        if role not in source:
            sanitized[role] = bool(default_value)
            continue
        value = source.get(role)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                sanitized[role] = True
                continue
            if lowered in {"0", "false", "no", "off", ""}:
                sanitized[role] = False
                continue
        sanitized[role] = bool(value)
    return sanitized


def _normalize_field_keys(raw: Any, defaults: dict[str, str]) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, str] = {}
    for semantic_key, default_key in defaults.items():
        value = str(source.get(semantic_key, "")).strip()[:64]
        if not value:
            value = default_key
        result[semantic_key] = value
    return result


def _normalize_notification_event(raw: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "key": str(source.get("key", defaults["key"])).strip()[:32] or defaults["key"],
        "label": str(source.get("label", defaults["label"])).strip()[:64] or defaults["label"],
        "desc": str(source.get("desc", defaults["desc"])).strip()[:255] or defaults["desc"],
        "enabled": bool(source.get("enabled", defaults["enabled"])),
        "template_id": str(source.get("template_id", "")).strip()[:128],
        "page": str(source.get("page", defaults["page"])).strip()[:255] or defaults["page"],
        "field_keys": _normalize_field_keys(source.get("field_keys"), defaults["field_keys"]),
        "field_mode": str(source.get("field_mode", defaults.get("field_mode", "editable"))).strip()[:32]
        or defaults.get("field_mode", "editable"),
        "field_note": str(source.get("field_note", defaults.get("field_note", ""))).strip()[:255]
        or defaults.get("field_note", ""),
    }


def _normalize_notification_settings(raw: Any) -> dict[str, Any]:
    base = default_notification_settings()
    if not isinstance(raw, dict):
        return base
    mini_source = raw.get("miniapp_subscribe")
    mini_defaults = base["miniapp_subscribe"]
    events_by_key = {item["key"]: item for item in DEFAULT_NOTIFICATION_EVENTS}
    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    if isinstance(mini_source, dict):
        raw_events = mini_source.get("events")
        if isinstance(raw_events, list):
            for item in raw_events:
                key = str(item.get("key", "")).strip() if isinstance(item, dict) else ""
                defaults = events_by_key.get(key)
                if not defaults:
                    continue
                events.append(_normalize_notification_event(item, defaults))
                seen.add(key)
    for defaults in DEFAULT_NOTIFICATION_EVENTS:
        if defaults["key"] not in seen:
            events.append(deepcopy(defaults))
    return {
        "enabled": bool(raw.get("enabled", base["enabled"])),
        "miniapp_subscribe": {
            "enabled": bool(mini_source.get("enabled", mini_defaults["enabled"])) if isinstance(mini_source, dict) else mini_defaults["enabled"],
            "events": events,
        },
    }


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def _int_value(value: Any, default: int, *, minimum: int = 0, maximum: int = 86400) -> int:
    try:
        result = int(value)
    except Exception:
        result = default
    return max(minimum, min(maximum, result))


def _str_value(value: Any, default: str = "", *, limit: int = 255) -> str:
    text = str(value if value is not None else default).strip()
    return text[:limit]


def _normalize_ai_model(model: str) -> str:
    normalized = model.strip()
    if not normalized:
        return "deepseek-v4-flash"
    if normalized in {"deepseek-chat", "deepseek-reasoner"}:
        return "deepseek-v4-flash"
    return normalized


def _normalize_ai_settings(raw: Any, previous: Any = None, *, include_secrets: bool = False) -> dict[str, Any]:
    defaults = default_ai_settings(include_secrets=True)
    source = raw if isinstance(raw, dict) else {}
    previous_source = previous if isinstance(previous, dict) else {}
    api_key = _str_value(source.get("api_key"), "", limit=512)
    if not api_key or set(api_key) == {"*"}:
        api_key = _str_value(previous_source.get("api_key"), defaults.get("api_key", ""), limit=512)
    result: dict[str, Any] = {
        "enabled": _bool_value(source.get("enabled"), bool(defaults["enabled"])),
        "dry_run": _bool_value(source.get("dry_run"), bool(defaults["dry_run"])),
        "provider": "deepseek",
        "base_url": _str_value(source.get("base_url"), str(defaults["base_url"]), limit=255),
        "model": _normalize_ai_model(_str_value(source.get("model"), str(defaults["model"]), limit=80)),
        "timeout_seconds": _int_value(source.get("timeout_seconds"), int(defaults["timeout_seconds"]), minimum=5, maximum=120),
        "max_output_tokens": _int_value(source.get("max_output_tokens"), int(defaults["max_output_tokens"]), minimum=200, maximum=8000),
        "api_key_set": bool(api_key),
    }
    if include_secrets:
        result["api_key"] = api_key
    return result


def _normalize_image_ai_settings(raw: Any, previous: Any = None, *, include_secrets: bool = False) -> dict[str, Any]:
    defaults = default_image_ai_settings(include_secrets=True)
    source = raw if isinstance(raw, dict) else {}
    previous_source = previous if isinstance(previous, dict) else {}
    api_key = _str_value(source.get("api_key"), "", limit=512)
    if not api_key or set(api_key) == {"*"}:
        api_key = _str_value(previous_source.get("api_key"), defaults.get("api_key", ""), limit=512)
    result: dict[str, Any] = {
        "enabled": _bool_value(source.get("enabled"), bool(defaults["enabled"])),
        "provider": "openai_compatible",
        "base_url": _str_value(source.get("base_url"), "", limit=255).rstrip("/"),
        "model": _str_value(source.get("model"), "", limit=120),
        "timeout_seconds": _int_value(source.get("timeout_seconds"), int(defaults["timeout_seconds"]), minimum=15, maximum=180),
        "max_input_images": _int_value(source.get("max_input_images"), int(defaults["max_input_images"]), minimum=1, maximum=5),
        "api_key_set": bool(api_key),
    }
    if include_secrets:
        result["api_key"] = api_key
    return result


def _normalize_system_settings(raw: Any) -> dict[str, Any]:
    defaults = default_system_settings()
    source = raw if isinstance(raw, dict) else {}

    def section(name: str) -> dict[str, Any]:
        value = source.get(name)
        return value if isinstance(value, dict) else {}

    app = section("app")
    auth = section("auth")
    scheduler = section("scheduler")
    wechat = section("wechat")
    print_settings = section("print")

    return {
        "app": {
            "app_env": _str_value(app.get("app_env"), defaults["app"]["app_env"], limit=32),
            "app_debug": _bool_value(app.get("app_debug"), defaults["app"]["app_debug"]),
            "public_asset_base_url": _str_value(app.get("public_asset_base_url"), defaults["app"]["public_asset_base_url"], limit=255),
        },
        "auth": {
            "auth_sms_mock": _bool_value(auth.get("auth_sms_mock"), defaults["auth"]["auth_sms_mock"]),
            "auth_sms_code_ttl_seconds": _int_value(auth.get("auth_sms_code_ttl_seconds"), defaults["auth"]["auth_sms_code_ttl_seconds"], minimum=60, maximum=3600),
            "auth_sms_resend_seconds": _int_value(auth.get("auth_sms_resend_seconds"), defaults["auth"]["auth_sms_resend_seconds"], minimum=10, maximum=600),
        },
        "scheduler": {
            "enabled": _bool_value(scheduler.get("enabled"), defaults["scheduler"]["enabled"]),
            "interval_seconds": _int_value(scheduler.get("interval_seconds"), defaults["scheduler"]["interval_seconds"], minimum=30, maximum=86400),
            "express_auto_complete_days": _int_value(scheduler.get("express_auto_complete_days"), defaults["scheduler"]["express_auto_complete_days"], minimum=1, maximum=60),
            "offline_auto_complete_days": _int_value(scheduler.get("offline_auto_complete_days"), defaults["scheduler"]["offline_auto_complete_days"], minimum=1, maximum=90),
        },
        "wechat": {
            "pay_mock": _bool_value(wechat.get("pay_mock"), defaults["wechat"]["pay_mock"]),
            "notification_channels": _str_value(wechat.get("notification_channels"), defaults["wechat"]["notification_channels"], limit=120),
            "mini_app_id": _str_value(wechat.get("mini_app_id"), defaults["wechat"]["mini_app_id"], limit=80),
            "app_id": _str_value(wechat.get("app_id"), defaults["wechat"]["app_id"], limit=80),
            "mch_id": _str_value(wechat.get("mch_id"), defaults["wechat"]["mch_id"], limit=80),
            "notify_url": _str_value(wechat.get("notify_url"), defaults["wechat"]["notify_url"], limit=255),
            "refund_notify_url": _str_value(wechat.get("refund_notify_url"), defaults["wechat"]["refund_notify_url"], limit=255),
        },
        "print": {
            "provider": _str_value(print_settings.get("provider"), defaults["print"]["provider"], limit=80),
            "job_ttl_seconds": _int_value(print_settings.get("job_ttl_seconds"), defaults["print"]["job_ttl_seconds"], minimum=3600, maximum=2592000),
        },
        "sensitive_status": defaults["sensitive_status"],
    }


def normalize_storefront_config(raw: Any, *, include_secrets: bool = False) -> dict[str, Any]:
    result = default_storefront_config(include_secrets=include_secrets)
    if not isinstance(raw, dict):
        return result
    result["home_banners"] = _normalize_banners(raw.get("home_banners"))
    result["login_page"] = _normalize_login_page(raw.get("login_page"))
    result["store_info"] = _normalize_store_info(raw.get("store_info"))
    result["customer_service"] = _normalize_customer_service(raw.get("customer_service"))
    result["shipping_thresholds"] = _normalize_shipping_thresholds(raw.get("shipping_thresholds"))
    result["shipping_thresholds_enabled"] = _normalize_shipping_threshold_switches(
        raw.get("shipping_thresholds_enabled")
    )
    result["shipping_rules"] = _normalize_shipping_rules(raw.get("shipping_rules"))
    if isinstance(raw.get("shipping_policy"), dict):
        result["shipping_policy"] = _normalize_shipping_policy(raw.get("shipping_policy"))
    if isinstance(raw.get("notification_settings"), dict):
        result["notification_settings"] = _normalize_notification_settings(raw.get("notification_settings"))
    if isinstance(raw.get("ai_settings"), dict):
        result["ai_settings"] = _normalize_ai_settings(raw.get("ai_settings"), raw.get("ai_settings"), include_secrets=include_secrets)
    if isinstance(raw.get("image_ai_settings"), dict):
        result["image_ai_settings"] = _normalize_image_ai_settings(raw.get("image_ai_settings"), raw.get("image_ai_settings"), include_secrets=include_secrets)
    result["print_layout"] = _normalize_print_layout(raw.get("print_layout"), result["print_layout"])
    if isinstance(raw.get("watermark"), dict):
        result["watermark"] = _normalize_watermark(raw.get("watermark"))
    if isinstance(raw.get("system_settings"), dict):
        result["system_settings"] = _normalize_system_settings(raw.get("system_settings"))
    updated_at = raw.get("updated_at")
    if updated_at is not None:
        result["updated_at"] = str(updated_at)
    return result


def merge_storefront_config(previous: Any, payload: Any) -> dict[str, Any]:
    result = normalize_storefront_config(previous, include_secrets=True)
    if not isinstance(payload, dict):
        return result

    if "home_banners" in payload:
        result["home_banners"] = _normalize_banners(payload.get("home_banners"))
    if "login_page" in payload:
        result["login_page"] = _normalize_login_page(payload.get("login_page"))
    if "store_info" in payload:
        result["store_info"] = _normalize_store_info(payload.get("store_info"))
    if "customer_service" in payload:
        result["customer_service"] = _normalize_customer_service(payload.get("customer_service"))
    if "shipping_thresholds" in payload:
        result["shipping_thresholds"] = _normalize_shipping_thresholds(payload.get("shipping_thresholds"))
    if "shipping_thresholds_enabled" in payload:
        result["shipping_thresholds_enabled"] = _normalize_shipping_threshold_switches(
            payload.get("shipping_thresholds_enabled")
        )
    if "shipping_rules" in payload:
        result["shipping_rules"] = _normalize_shipping_rules(payload.get("shipping_rules"))
    if "shipping_policy" in payload:
        result["shipping_policy"] = _normalize_shipping_policy(payload.get("shipping_policy"))
    if "notification_settings" in payload:
        result["notification_settings"] = _normalize_notification_settings(payload.get("notification_settings"))
    if "ai_settings" in payload:
        previous_ai = previous.get("ai_settings") if isinstance(previous, dict) else None
        result["ai_settings"] = _normalize_ai_settings(payload.get("ai_settings"), previous_ai, include_secrets=True)
    if "image_ai_settings" in payload:
        previous_image_ai = previous.get("image_ai_settings") if isinstance(previous, dict) else None
        result["image_ai_settings"] = _normalize_image_ai_settings(payload.get("image_ai_settings"), previous_image_ai, include_secrets=True)
    if "print_layout" in payload:
        result["print_layout"] = _normalize_print_layout(payload.get("print_layout"), result["print_layout"])
    if "watermark" in payload:
        result["watermark"] = _normalize_watermark(payload.get("watermark"))
    if "system_settings" in payload:
        result["system_settings"] = _normalize_system_settings(payload.get("system_settings"))

    result["updated_at"] = datetime.now(UTC).isoformat()
    return result


def load_storefront_config(*, include_secrets: bool = False) -> dict[str, Any]:
    if not STOREFRONT_CONFIG_PATH.exists():
        return default_storefront_config(include_secrets=include_secrets)
    try:
        raw = STOREFRONT_CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw else {}
        return normalize_storefront_config(data, include_secrets=include_secrets)
    except Exception:
        return default_storefront_config(include_secrets=include_secrets)


def public_storefront_config(data: Any) -> dict[str, Any]:
    result = normalize_storefront_config(data, include_secrets=False)
    result.pop("ai_settings", None)
    result.pop("image_ai_settings", None)
    result.pop("system_settings", None)
    result.pop("print_layout", None)
    return result


def load_admin_ai_runtime_settings() -> dict[str, Any]:
    return load_storefront_config(include_secrets=True).get("ai_settings", default_ai_settings(include_secrets=True))
