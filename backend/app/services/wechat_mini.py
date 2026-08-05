import asyncio
import json
from urllib import parse, request
from urllib.error import HTTPError

from app.core.config import get_settings
from app.core.exceptions import bad_request


def _require_mini_config(app_scope: str = "customer") -> tuple[str, str]:
    settings = get_settings()
    app_id = settings.WECHAT_EMPLOYEE_MINI_APP_ID if app_scope == "employee" else (settings.WECHAT_MINI_APP_ID or settings.WECHAT_APP_ID)
    app_secret = settings.WECHAT_EMPLOYEE_MINI_APP_SECRET if app_scope == "employee" else settings.WECHAT_MINI_APP_SECRET
    if not app_id or not app_secret:
        raise bad_request("wechat mini app config missing")
    return app_id, app_secret


async def fetch_access_token(app_scope: str = "customer") -> str:
    app_id, app_secret = _require_mini_config(app_scope)
    query = parse.urlencode(
        {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        }
    )
    url = f"https://api.weixin.qq.com/cgi-bin/token?{query}"

    def _run() -> dict:
        req = request.Request(url=url, method="GET", headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = str(e)
            raise bad_request(f"wechat get access_token http error {e.code}: {body}") from e

    result = await asyncio.to_thread(_run)
    if result.get("errcode"):
        raise bad_request(f"wechat get access_token failed: {result.get('errmsg')}")
    token = result.get("access_token")
    if not token:
        raise bad_request("wechat get access_token missing access_token")
    return token


async def code_to_session(code: str, app_scope: str = "customer") -> dict:
    app_id, app_secret = _require_mini_config(app_scope)

    query = parse.urlencode(
        {
            "appid": app_id,
            "secret": app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"

    def _run() -> dict:
        req = request.Request(url=url, method="GET", headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = str(e)
            raise bad_request(f"wechat code2session http error {e.code}: {body}") from e

    result = await asyncio.to_thread(_run)
    if result.get("errcode"):
        raise bad_request(f"wechat code2session failed: {result.get('errmsg')}")
    if not result.get("openid"):
        raise bad_request("wechat code2session missing openid")
    return result


async def get_phone_number(phone_code: str, app_scope: str = "customer") -> str:
    access_token = await fetch_access_token(app_scope)
    url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}"
    body = json.dumps({"code": phone_code}).encode("utf-8")

    def _run() -> dict:
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
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                body_text = str(e)
            raise bad_request(f"wechat get phone http error {e.code}: {body_text}") from e

    result = await asyncio.to_thread(_run)
    if result.get("errcode"):
        raise bad_request(f"wechat get phone failed: {result.get('errmsg')}")

    phone_info = result.get("phone_info") or {}
    phone = phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")
    if not phone:
        raise bad_request("wechat get phone missing phone")
    return phone
