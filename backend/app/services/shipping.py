from decimal import Decimal
import json
from pathlib import Path

from app.models.enums import UserRole

STOREFRONT_CONFIG_PATH = Path("/app/data/storefront-config.json")


def _to_decimal(value: object, fallback: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(fallback)


def _read_storefront_shipping_config() -> dict:
    defaults = {
        "role_specific": False,
        "delivery_fee": "8.00",
        "free_shipping_threshold": "99.00",
        "retail": {"delivery_fee": "8.00", "free_shipping_threshold": "99.00"},
        "wholesale": {"delivery_fee": "8.00", "free_shipping_threshold": "99.00"},
    }
    try:
        if not STOREFRONT_CONFIG_PATH.exists():
            return defaults
        raw = STOREFRONT_CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            return defaults
        policy = data.get("shipping_policy")
        if not isinstance(policy, dict):
            return defaults
        return policy
    except Exception:
        return defaults


def _policy_amount(config: dict, role: UserRole, key: str, fallback: str) -> Decimal:
    value = config.get(key, fallback)
    if config.get("role_specific") is True:
        role_key = "wholesale" if role == UserRole.WHOLESALE else "retail"
        role_policy = config.get(role_key)
        if isinstance(role_policy, dict):
            value = role_policy.get(key, value)
    return _to_decimal(value, fallback)


def get_shipping_threshold(
    *,
    role: UserRole,
    retail_free_threshold: Decimal | None = None,
    wholesale_free_threshold: Decimal | None = None,
) -> Decimal:
    _ = role
    config = _read_storefront_shipping_config()
    override = wholesale_free_threshold if role == UserRole.WHOLESALE else retail_free_threshold
    if override is not None:
        return _to_decimal(override, "99.00")
    return _policy_amount(config, role, "free_shipping_threshold", "99.00")


def calculate_shipping_fee(
    *,
    role: UserRole,
    merchandise_amount: Decimal,
    shipping_channel: str = "express",
    retail_free_threshold: Decimal | None = None,
    wholesale_free_threshold: Decimal | None = None,
    retail_base_fee: Decimal = Decimal("8.00"),
) -> Decimal:
    channel = "pickup" if shipping_channel == "pickup" else "delivery"
    if channel == "pickup":
        return Decimal("0.00")
    free_threshold = get_shipping_threshold(
        role=role,
        retail_free_threshold=retail_free_threshold,
        wholesale_free_threshold=wholesale_free_threshold,
    )
    configured_fee = _policy_amount(_read_storefront_shipping_config(), role, "delivery_fee", "8.00")
    if channel != "pickup" and free_threshold > Decimal("0.00") and merchandise_amount >= free_threshold:
        return Decimal("0.00")
    _ = retail_base_fee
    return configured_fee
