from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import CustomerProfile, User
from app.schemas.auth import CurrentUserResponse, SelfPasswordUpdateIn, SelfProfileUpdateIn

router = APIRouter(prefix="/admin", tags=["admin"])


def _serialize_current_user(user: User) -> CurrentUserResponse:
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


@router.patch("/me/profile", response_model=CurrentUserResponse, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_admin_profile(
    payload: SelfProfileUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")

    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user.profile, key, value)

    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_current_user(user)


@router.patch("/me/password", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_admin_password(
    payload: SelfPasswordUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.scalar(select(User).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    if not verify_password(payload.current_password, user.password_hash):
        raise bad_request("current password is incorrect")
    if payload.current_password == payload.new_password:
        raise bad_request("new password must be different from current password")

    user.password_hash = get_password_hash(payload.new_password)
    user.session_version += 1
    await db.commit()
    return {"id": user.id, "updated": True}
