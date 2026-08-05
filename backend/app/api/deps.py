from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import forbidden, unauthorized
from app.core.rate_limit import redis_client
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

# auto_error=False allows us to implement mini-program compatible fallbacks.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    raw = auth_header.strip()
    if not raw:
        return None
    if raw.lower().startswith("bearer "):
        return raw[7:].strip() or None
    return raw


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    # 1) standard OAuth2 Authorization: Bearer <token>
    # 2) fallback for some mini-program/http clients that pass token in custom headers.
    if not token:
        token = _extract_bearer_token(request.headers.get("authorization"))
    if not token:
        token = _extract_bearer_token(request.headers.get("token"))
    if not token:
        token = _extract_bearer_token(request.headers.get("x-token"))
    if not token:
        raise unauthorized("Not authenticated")
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise unauthorized("Invalid token") from exc
    username = payload.get("sub")
    if not username:
        raise unauthorized("Invalid token payload")
    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.username == username, User.is_active.is_(True))
    )
    if not user:
        raise unauthorized("User not found or inactive")
    try:
        token_session_version = int(payload.get("sv", 1))
    except (TypeError, ValueError):
        raise unauthorized("Invalid token payload")
    if token_session_version != user.session_version:
        raise unauthorized("Login session expired")
    if user.role in {UserRole.RETAIL, UserRole.WHOLESALE} and user.is_blacklisted:
        raise forbidden("Account is blacklisted")
    return user


def require_roles(allowed: set[UserRole]) -> Callable:
    async def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise forbidden("Insufficient role permission")
        return user

    return _check


async def wholesale_price_limit(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if user.role not in {UserRole.ADMIN, UserRole.WHOLESALE}:
        return
    key = f"wholesale-price:{user.id}:{request.client.host if request.client else 'unknown'}"
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, 60)
        if current > 30:
            # soft ban 10 minutes
            await redis_client.setex(f"wholesale-ban:{user.id}", 600, "1")
            raise forbidden("Wholesale price access temporarily blocked")
        banned = await redis_client.get(f"wholesale-ban:{user.id}")
        if banned:
            raise forbidden("Wholesale price access temporarily blocked")
    except RedisError:
        return
