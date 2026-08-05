import asyncio
import base64
import json
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from urllib.error import HTTPError
from urllib import request
from urllib.parse import quote

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.exceptions import bad_request


@dataclass
class WechatCreateResult:
    prepay_id: str | None = None
    code_url: str | None = None
    raw: dict | None = None


def _nonce() -> str:
    return uuid.uuid4().hex


def _timestamp() -> str:
    return str(int(time.time()))


def _build_auth_header(method: str, url_path: str, body_json: str) -> str:
    settings = get_settings()
    if not settings.WECHAT_PRIVATE_KEY_PATH:
        raise bad_request("wechat private key path not configured")
    if not settings.WECHAT_MCH_ID or not settings.WECHAT_SERIAL_NO:
        raise bad_request("wechat merchant config missing")

    with open(settings.WECHAT_PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    ts = _timestamp()
    nonce = _nonce()
    sign_message = f"{method}\n{url_path}\n{ts}\n{nonce}\n{body_json}\n".encode("utf-8")
    signature = private_key.sign(sign_message, padding.PKCS1v15(), hashes.SHA256())
    sign = base64.b64encode(signature).decode("utf-8")
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{settings.WECHAT_MCH_ID}",'
        f'nonce_str="{nonce}",timestamp="{ts}",serial_no="{settings.WECHAT_SERIAL_NO}",signature="{sign}"'
    )


def build_jsapi_pay_params(prepay_id: str) -> dict:
    settings = get_settings()
    if not settings.WECHAT_APP_ID:
        raise bad_request("wechat app_id missing")
    if not settings.WECHAT_PRIVATE_KEY_PATH:
        raise bad_request("wechat private key path not configured")

    with open(settings.WECHAT_PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    ts = _timestamp()
    nonce = _nonce()
    pkg = f"prepay_id={prepay_id}"
    sign_message = f"{settings.WECHAT_APP_ID}\n{ts}\n{nonce}\n{pkg}\n".encode("utf-8")
    sign = base64.b64encode(private_key.sign(sign_message, padding.PKCS1v15(), hashes.SHA256())).decode("utf-8")
    return {
        "appId": settings.WECHAT_APP_ID,
        "timeStamp": ts,
        "nonceStr": nonce,
        "package": pkg,
        "signType": "RSA",
        "paySign": sign,
    }


async def _post_wechat_v3(url_path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    auth = _build_auth_header("POST", url_path, body)
    req = request.Request(
        url=f"https://api.mch.weixin.qq.com{url_path}",
        method="POST",
        data=body.encode("utf-8"),
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "yyy-hub/0.1",
        },
    )

    def _run() -> dict:
        try:
            with request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = str(e)
            raise bad_request(f"wechat v3 error {e.code}: {body}") from e

    return await asyncio.to_thread(_run)


def amount_to_fen(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1")))


async def create_jsapi_transaction(
    order_no: str,
    amount: Decimal,
    openid: str,
    description: str | None = None,
) -> WechatCreateResult:
    settings = get_settings()
    if not settings.WECHAT_APP_ID or not settings.WECHAT_MCH_ID:
        raise bad_request("wechat app_id or mch_id missing")
    if not settings.WECHAT_NOTIFY_URL:
        raise bad_request("wechat notify url missing")
    if not openid:
        raise bad_request("openid is required for jsapi")

    payload = {
        "appid": settings.WECHAT_APP_ID,
        "mchid": settings.WECHAT_MCH_ID,
        "description": description or f"Order {order_no}",
        "out_trade_no": order_no,
        "notify_url": settings.WECHAT_NOTIFY_URL,
        "amount": {"total": amount_to_fen(amount), "currency": "CNY"},
        "payer": {"openid": openid},
    }
    data = await _post_wechat_v3("/v3/pay/transactions/jsapi", payload)
    return WechatCreateResult(prepay_id=data.get("prepay_id"), raw=data)


async def create_native_transaction(
    order_no: str,
    amount: Decimal,
    description: str | None = None,
) -> WechatCreateResult:
    settings = get_settings()
    if not settings.WECHAT_APP_ID or not settings.WECHAT_MCH_ID:
        raise bad_request("wechat app_id or mch_id missing")
    if not settings.WECHAT_NOTIFY_URL:
        raise bad_request("wechat notify url missing")

    payload = {
        "appid": settings.WECHAT_APP_ID,
        "mchid": settings.WECHAT_MCH_ID,
        "description": description or f"Order {order_no}",
        "out_trade_no": order_no,
        "notify_url": settings.WECHAT_NOTIFY_URL,
        "amount": {"total": amount_to_fen(amount), "currency": "CNY"},
    }
    data = await _post_wechat_v3("/v3/pay/transactions/native", payload)
    return WechatCreateResult(code_url=data.get("code_url"), raw=data)


async def query_transaction_by_out_trade_no(out_trade_no: str) -> dict:
    settings = get_settings()
    if not settings.WECHAT_MCH_ID:
        raise bad_request("wechat mch_id missing")
    encoded_trade_no = quote(out_trade_no, safe="")
    query_path = f"/v3/pay/transactions/out-trade-no/{encoded_trade_no}?mchid={settings.WECHAT_MCH_ID}"
    auth = _build_auth_header("GET", query_path, "")
    req = request.Request(
        url=f"https://api.mch.weixin.qq.com{query_path}",
        method="GET",
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "yyy-hub/0.1",
        },
    )

    def _run() -> dict:
        try:
            with request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = str(e)
            raise bad_request(f"wechat v3 query error {e.code}: {body}") from e

    return await asyncio.to_thread(_run)


async def create_refund_transaction(
    out_trade_no: str,
    out_refund_no: str,
    total_amount: Decimal,
    refund_amount: Decimal,
    reason: str | None = None,
) -> dict:
    settings = get_settings()
    if not settings.WECHAT_MCH_ID:
        raise bad_request("wechat mch_id missing")
    payload = {
        "out_trade_no": out_trade_no,
        "out_refund_no": out_refund_no,
        "reason": reason or f"refund for {out_trade_no}",
        "notify_url": settings.WECHAT_REFUND_NOTIFY_URL or settings.WECHAT_NOTIFY_URL,
        "amount": {
            "refund": amount_to_fen(refund_amount),
            "total": amount_to_fen(total_amount),
            "currency": "CNY",
        },
    }
    return await _post_wechat_v3("/v3/refund/domestic/refunds", payload)


def verify_wechatpay_signature(headers: dict, body_text: str) -> None:
    settings = get_settings()
    normalized_headers = {str(key).lower(): value for key, value in headers.items()}
    signature = normalized_headers.get("wechatpay-signature")
    serial = normalized_headers.get("wechatpay-serial")
    timestamp = normalized_headers.get("wechatpay-timestamp")
    nonce = normalized_headers.get("wechatpay-nonce")
    if not signature or not serial or not timestamp or not nonce:
        raise bad_request("wechatpay signature headers missing")

    message = f"{timestamp}\n{nonce}\n{body_text}\n".encode("utf-8")
    sig = base64.b64decode(signature)

    verifier_sources: list[tuple[str, object]] = []
    if settings.WECHAT_PAY_PUBLIC_KEY_PATH:
        with open(settings.WECHAT_PAY_PUBLIC_KEY_PATH, "rb") as f:
            verifier_sources.append(("public_key", serialization.load_pem_public_key(f.read())))
    if settings.WECHAT_PLATFORM_CERT_PATH:
        with open(settings.WECHAT_PLATFORM_CERT_PATH, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        verifier_sources.append(("platform_cert", cert.public_key()))
    if not verifier_sources:
        raise bad_request("wechat verifier key not configured")

    last_error: Exception | None = None
    for _, pub_key in verifier_sources:
        try:
            pub_key.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())
            return
        except Exception as error:
            last_error = error

    raise bad_request("invalid wechatpay signature") from last_error


def decrypt_wechat_resource(body: dict) -> dict:
    settings = get_settings()
    if not settings.WECHAT_API_V3_KEY:
        raise bad_request("wechat api v3 key missing")
    resource = body.get("resource") or {}
    ciphertext = resource.get("ciphertext")
    nonce = resource.get("nonce")
    associated_data = resource.get("associated_data", "")
    if not ciphertext or not nonce:
        raise bad_request("invalid wechat resource")

    aesgcm = AESGCM(settings.WECHAT_API_V3_KEY.encode("utf-8"))
    plain = aesgcm.decrypt(
        nonce.encode("utf-8"),
        base64.b64decode(ciphertext),
        associated_data.encode("utf-8"),
    )
    return json.loads(plain.decode("utf-8"))
