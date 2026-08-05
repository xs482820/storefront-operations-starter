from collections.abc import Sequence
import secrets
import string
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.exceptions import bad_request, unauthorized
from app.core.rate_limit import redis_client
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import CustomerProfile, User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    PhoneCodeRequestIn,
    PhoneCodeRequestOut,
    PhoneCodeVerifyIn,
    RegisterRequest,
    TokenResponse,
    WechatMiniCodeIn,
    WechatMiniCodeOut,
    WechatMiniBindPhoneIn,
    WechatMiniBindPhoneOut,
    WechatMiniLoginIn,
    WechatMiniLoginWithPhoneIn,
    normalize_phone,
)
from app.services.wechat_mini import code_to_session, get_phone_number

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

LOGIN_FAIL_LIMIT = 8
LOGIN_FAIL_WINDOW_SECONDS = 10 * 60
LOGIN_LOCK_SECONDS = 15 * 60


def _code_key(phone: str, purpose: str) -> str:
    return f"auth:sms:code:{purpose}:{phone}"


def _cooldown_key(phone: str, purpose: str) -> str:
    return f"auth:sms:cooldown:{purpose}:{phone}"


def _login_fail_key(identifier: str, ip: str) -> str:
    normalized_identifier = identifier.strip().lower()
    return f"auth:login:fail:{ip}:{normalized_identifier}"


def _login_lock_key(identifier: str, ip: str) -> str:
    normalized_identifier = identifier.strip().lower()
    return f"auth:login:lock:{ip}:{normalized_identifier}"


def _request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _generate_backup_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    normalized_phone = None
    try:
        normalized_phone = normalize_phone(identifier)
    except ValueError:
        normalized_phone = None

    condition = User.username == identifier
    if normalized_phone:
        condition = or_(condition, CustomerProfile.phone == normalized_phone)

    stmt = (
        select(User)
        .outerjoin(CustomerProfile, CustomerProfile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(
            User.is_active.is_(True),
            condition,
        )
        .limit(1)
    )
    return await db.scalar(stmt)


async def _build_token_response(user: User, generated_password: str | None = None, is_new_user: bool = False) -> TokenResponse:
    token = create_access_token(subject=user.username)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        phone=user.profile.phone if user.profile else None,
        wechat_openid=user.profile.wechat_openid if user.profile else None,
        wechat_bound=bool(user.profile.wechat_openid if user.profile else None),
        is_new_user=is_new_user,
        generated_password=generated_password,
    )


async def _generate_unique_username(db: AsyncSession, phone: str) -> str:
    base = f"u{phone}"
    candidate = base
    index = 1
    while await db.scalar(select(User.id).where(User.username == candidate)):
        index += 1
        candidate = f"{base}_{index}"
    return candidate


async def _generate_wechat_username(db: AsyncSession, openid: str) -> str:
    base = f"wx_{openid[-8:]}".lower()
    candidate = base
    index = 1
    while await db.scalar(select(User.id).where(User.username == candidate)):
        index += 1
        candidate = f"{base}_{index}"
    return candidate


async def _find_user_by_wechat_identity(db: AsyncSession, openid: str, unionid: str | None) -> User | None:
    return await db.scalar(
        select(User)
        .join(CustomerProfile, CustomerProfile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(
            User.is_active.is_(True),
            (CustomerProfile.wechat_openid == openid)
            | ((CustomerProfile.wechat_unionid == unionid) if unionid else false()),
        )
        .limit(1)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    identifier = (payload.identifier or payload.username or "").strip()
    if not identifier:
        raise unauthorized("Invalid account, phone, or password")

    ip = _request_ip(request)
    lock_key = _login_lock_key(identifier, ip)
    lock_ttl = await redis_client.ttl(lock_key)
    if lock_ttl and lock_ttl > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Login temporarily locked, please retry after {lock_ttl} seconds",
        )

    user = await _find_user_by_identifier(db, identifier)
    if not user or not verify_password(payload.password, user.password_hash):
        fail_key = _login_fail_key(identifier, ip)
        current = await redis_client.incr(fail_key)
        if current == 1:
            await redis_client.expire(fail_key, LOGIN_FAIL_WINDOW_SECONDS)
        if current >= LOGIN_FAIL_LIMIT:
            await redis_client.setex(lock_key, LOGIN_LOCK_SECONDS, "1")
            await redis_client.delete(fail_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts, please try again later",
            )
        raise unauthorized("Invalid account, phone, or password")
    await redis_client.delete(_login_fail_key(identifier, ip))
    await redis_client.delete(lock_key)
    return await _build_token_response(user)


@router.post("/register", response_model=TokenResponse)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    exists = await db.scalar(select(CustomerProfile.id).where(CustomerProfile.phone == payload.phone))
    if exists:
        raise bad_request("phone already registered")

    username = await _generate_unique_username(db, payload.phone)
    generated_password = _generate_backup_password()

    user = User(
        username=username,
        password_hash=get_password_hash(generated_password),
        role=UserRole.RETAIL,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    db.add(
        CustomerProfile(
            user_id=user.id,
            display_name=payload.display_name,
            phone=payload.phone,
            is_verified_wholesale=False,
        )
    )
    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
    if not user:
        raise unauthorized("user create failed")
    return await _build_token_response(user, generated_password=generated_password, is_new_user=True)


@router.post("/phone/request-code", response_model=PhoneCodeRequestOut)
async def request_phone_code(payload: PhoneCodeRequestIn) -> PhoneCodeRequestOut:
    cooldown = await redis_client.ttl(_cooldown_key(payload.phone, payload.purpose))
    if cooldown and cooldown > 0:
        raise bad_request(f"please retry after {cooldown} seconds")

    code = f"{secrets.randbelow(900000) + 100000}"
    await redis_client.setex(_code_key(payload.phone, payload.purpose), settings.AUTH_SMS_CODE_TTL_SECONDS, code)
    await redis_client.setex(_cooldown_key(payload.phone, payload.purpose), settings.AUTH_SMS_RESEND_SECONDS, "1")
    return PhoneCodeRequestOut(
        phone=_mask_phone(payload.phone) or payload.phone,
        purpose=payload.purpose,
        expires_seconds=settings.AUTH_SMS_CODE_TTL_SECONDS,
        retry_after_seconds=settings.AUTH_SMS_RESEND_SECONDS,
        debug_code=code if settings.AUTH_SMS_MOCK else None,
    )


@router.post("/phone/verify", response_model=TokenResponse)
async def verify_phone_code(
    payload: PhoneCodeVerifyIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    stored_code = await redis_client.get(_code_key(payload.phone, "login"))
    if not stored_code or stored_code != payload.code:
        raise unauthorized("invalid or expired sms code")

    user = await db.scalar(
        select(User)
        .join(CustomerProfile, CustomerProfile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(CustomerProfile.phone == payload.phone, User.is_active.is_(True))
        .limit(1)
    )
    generated_password = None
    is_new_user = False
    if not user:
        username = await _generate_unique_username(db, payload.phone)
        generated_password = _generate_backup_password()
        user = User(
            username=username,
            password_hash=get_password_hash(generated_password),
            role=UserRole.RETAIL,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            CustomerProfile(
                user_id=user.id,
                display_name=payload.display_name or f"用户{payload.phone[-4:]}",
                phone=payload.phone,
                is_verified_wholesale=False,
            )
        )
        await db.commit()
        user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
        is_new_user = True

    await redis_client.delete(_code_key(payload.phone, "login"))
    if not user:
        raise unauthorized("user not found")
    return await _build_token_response(user, generated_password=generated_password, is_new_user=is_new_user)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUserResponse:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise unauthorized("user not found")
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.profile.display_name if user.profile else None,
        avatar_url=user.profile.avatar_url if user.profile else None,
        phone=user.profile.phone if user.profile else None,
        wechat_openid=user.profile.wechat_openid if user.profile else None,
        wechat_bound=bool(user.profile.wechat_openid if user.profile else None),
    )


@router.post("/bootstrap-admin", response_model=CurrentUserResponse)
async def bootstrap_admin(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUserResponse:
    existing_users: Sequence[User] = (await db.scalars(select(User).limit(1))).all()
    if existing_users:
        raise unauthorized("Bootstrap endpoint disabled after first user created")

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return CurrentUserResponse(id=user.id, username=user.username, role=user.role, phone=None)


@router.post("/wechat/mini/code2session", response_model=WechatMiniCodeOut)
async def wechat_mini_code2session(payload: WechatMiniCodeIn) -> WechatMiniCodeOut:
    result = await code_to_session(payload.code)
    return WechatMiniCodeOut(
        openid=result["openid"],
        unionid=result.get("unionid"),
        session_key_present=bool(result.get("session_key")),
    )


@router.post("/wechat/mini/login", response_model=TokenResponse)
async def wechat_mini_login(
    payload: WechatMiniLoginIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    result = await code_to_session(payload.code)
    openid = result["openid"]
    unionid = result.get("unionid")

    user = await db.scalar(
        select(User)
        .join(CustomerProfile, CustomerProfile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(
            User.is_active.is_(True),
            (CustomerProfile.wechat_openid == openid)
            | ((CustomerProfile.wechat_unionid == unionid) if unionid else false()),
        )
        .limit(1)
    )

    is_new_user = False
    if not user:
        username = await _generate_wechat_username(db, openid)
        user = User(
            username=username,
            password_hash=get_password_hash(_generate_backup_password()),
            role=UserRole.RETAIL,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            CustomerProfile(
                user_id=user.id,
                display_name=(payload.display_name or "").strip() or f"微信用户{openid[-4:]}",
                wechat_openid=openid,
                wechat_unionid=unionid,
                is_verified_wholesale=False,
            )
        )
        await db.commit()
        user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
        is_new_user = True
    elif user.profile:
        user.profile.wechat_openid = openid
        if unionid:
            user.profile.wechat_unionid = unionid
        if payload.display_name and not user.profile.display_name:
            user.profile.display_name = payload.display_name.strip()
        await db.commit()
        user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))

    if not user:
        raise unauthorized("wechat login failed")
    return await _build_token_response(user, is_new_user=is_new_user)


@router.post("/wechat/mini/login-with-phone", response_model=TokenResponse)
async def wechat_mini_login_with_phone(
    payload: WechatMiniLoginWithPhoneIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    session_result = await code_to_session(payload.login_code)
    openid = session_result["openid"]
    unionid = session_result.get("unionid")
    phone = normalize_phone(await get_phone_number(payload.phone_code))

    user = await _find_user_by_wechat_identity(db, openid, unionid)
    is_new_user = False

    if not user:
        user = await db.scalar(
            select(User)
            .join(CustomerProfile, CustomerProfile.user_id == User.id)
            .options(selectinload(User.profile))
            .where(User.is_active.is_(True), CustomerProfile.phone == phone)
            .limit(1)
        )

    if not user:
        username = await _generate_unique_username(db, phone)
        user = User(
            username=username,
            password_hash=get_password_hash(_generate_backup_password()),
            role=UserRole.RETAIL,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            CustomerProfile(
                user_id=user.id,
                display_name=(payload.display_name or "").strip() or f"user_{phone[-4:]}",
                phone=phone,
                wechat_openid=openid,
                wechat_unionid=unionid,
                is_verified_wholesale=False,
            )
        )
        await db.commit()
        user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
        is_new_user = True
    else:
        if not user.profile:
            user.profile = CustomerProfile(user_id=user.id)
            db.add(user.profile)
            await db.flush()
        user.profile.phone = phone
        user.profile.wechat_openid = openid
        if unionid:
            user.profile.wechat_unionid = unionid
        if payload.display_name and not user.profile.display_name:
            user.profile.display_name = payload.display_name.strip()
        await db.commit()
        user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))

    if not user:
        raise unauthorized("wechat login failed")
    return await _build_token_response(user, is_new_user=is_new_user)


@router.post("/wechat/mini/bind-phone", response_model=WechatMiniBindPhoneOut)
async def wechat_mini_bind_phone(
    payload: WechatMiniBindPhoneIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WechatMiniBindPhoneOut:
    phone = normalize_phone(await get_phone_number(payload.code))
    existing = await db.scalar(
        select(CustomerProfile.id).where(
            CustomerProfile.phone == phone,
            CustomerProfile.user_id != current_user.id,
        )
    )
    if existing:
        raise bad_request("phone already bound by another user")

    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise unauthorized("user not found")
    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()
    user.profile.phone = phone
    await db.commit()
    return WechatMiniBindPhoneOut(bound=True, phone=phone)
