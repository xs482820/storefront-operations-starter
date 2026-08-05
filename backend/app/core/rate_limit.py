import hashlib
from collections.abc import Awaitable, Callable

import redis.asyncio as redis
from fastapi import Request, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.security import decode_access_token

settings = get_settings()
redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def _token_subject(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return "anonymous"
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        return str(payload.get("sub") or "anonymous")
    except Exception:
        return "anonymous"


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def _policy_for_path(path: str) -> tuple[int, int, int]:
    # limit, window_seconds, ban_seconds
    if path.startswith("/api/v1/payments/wechat/jsapi"):
        return (20, 60, 600)
    if path.startswith("/api/v1/payments/wechat/native"):
        return (20, 60, 600)
    if path.startswith("/api/v1/payments/wechat/refund"):
        return (15, 60, 600)
    if path.startswith("/api/v1/products"):
        return (180, 60, 120)
    return (120, 60, 0)


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable],
):
    path = request.url.path
    ip = request.client.host if request.client else "unknown"
    sub = _token_subject(request)
    uid = _sha1(sub)
    limit, window_seconds, ban_seconds = _policy_for_path(path)

    bucket = _sha1(path)
    base = f"ratelimit:{bucket}:{ip}:{uid}"
    count_key = f"{base}:count"
    ban_key = f"{base}:ban"
    try:
        ban_ttl = await redis_client.ttl(ban_key)
        if ban_ttl and ban_ttl > 0:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": f"Rate limited (banned {ban_ttl}s)"},
            )

        current = await redis_client.incr(count_key)
        if current == 1:
            await redis_client.expire(count_key, window_seconds)
        if current > limit:
            if ban_seconds > 0:
                await redis_client.setex(ban_key, ban_seconds, "1")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
    except RedisError:
        # Fail-open to keep API alive when Redis is temporarily unavailable.
        pass
    return await call_next(request)
