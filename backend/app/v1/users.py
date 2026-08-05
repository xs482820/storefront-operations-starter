from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.product import Inventory, Product, ProductSKU, SKUUnitConversion
from app.models.user import CustomerAddress, CustomerProfile, ShoppingCartItem, User, WholesaleApplication
from app.schemas.auth import normalize_phone
from app.schemas.user import (
    CustomerAddressCreateIn,
    CustomerAddressOut,
    CustomerAddressUpdateIn,
    CustomerCreateIn,
    CustomerProfileOut,
    CustomerSelfProfileUpdateIn,
    CustomerSelfPasswordUpdateIn,
    CustomerProfileUpdateIn,
    ShoppingCartItemOut,
    ShoppingCartSyncIn,
    WholesaleApplicationCreateIn,
    WholesaleApplicationOut,
    WholesaleApplicationReviewIn,
    UserAdminOut,
    UserRoleAssignIn,
    UserStatusUpdateIn,
)

router = APIRouter(prefix="/users", tags=["users"])


def _serialize_user(item: User) -> UserAdminOut:
    profile = None
    if item.profile:
        profile = CustomerProfileOut(
            display_name=item.profile.display_name,
            phone=item.profile.phone,
            company_name=item.profile.company_name,
            contact_name=item.profile.contact_name,
            address=item.profile.address,
            note=item.profile.note,
            avatar_url=item.profile.avatar_url,
            wechat_bound=bool(item.profile.wechat_openid),
            wechat_openid=item.profile.wechat_openid,
            is_verified_wholesale=item.profile.is_verified_wholesale,
        )
    return UserAdminOut(
        id=item.id,
        username=item.username,
        role=item.role,
        is_active=item.is_active,
        created_at=item.created_at.isoformat(),
        profile=profile,
    )


def _serialize_address(item: CustomerAddress) -> CustomerAddressOut:
    return CustomerAddressOut(
        id=item.id,
        recipient=item.recipient,
        phone=item.phone,
        province=item.province,
        city=item.city,
        district=item.district,
        detail=item.detail,
        is_default=item.is_default,
    )


async def _ensure_single_default_address(db: AsyncSession, user_id: int, current_id: int | None = None) -> None:
    rows = (
        await db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user_id)
            .order_by(CustomerAddress.id.asc())
        )
    ).all()
    if not rows:
        return
    target = None
    if current_id is not None:
        target = next((item for item in rows if item.id == current_id), None)
    if target is None:
        target = next((item for item in rows if item.is_default), None) or rows[0]
    for item in rows:
        item.is_default = item.id == target.id


async def _serialize_cart_items(db: AsyncSession, user_id: int) -> list[ShoppingCartItemOut]:
    rows = (
        await db.execute(
            select(ShoppingCartItem, Product, ProductSKU, Inventory)
            .join(ProductSKU, ProductSKU.id == ShoppingCartItem.sku_id)
            .join(Product, Product.id == ProductSKU.product_id)
            .join(Inventory, Inventory.sku_id == ProductSKU.id)
            .where(ShoppingCartItem.user_id == user_id)
            .order_by(ShoppingCartItem.id.desc())
        )
    ).all()
    if not rows:
        return []

    sku_ids = sorted({sku.id for _, _, sku, _ in rows})
    conversions = (
        await db.scalars(
            select(SKUUnitConversion)
            .where(SKUUnitConversion.sku_id.in_(sku_ids))
            .options(selectinload(SKUUnitConversion.unit))
        )
    ).all()
    conversion_map: dict[int, list[dict]] = {}
    for item in conversions:
        if not item.unit:
            continue
        conversion_map.setdefault(item.sku_id, []).append(
            {
                "unit_code": item.unit.code,
                "unit_name": item.unit.name,
                "to_base_factor": item.to_base_factor,
                "is_base_unit": item.is_base_unit,
            }
        )

    out: list[ShoppingCartItemOut] = []
    for cart_item, product, sku, inventory in rows:
        convs = conversion_map.get(sku.id, [])
        selected_unit = next((it for it in convs if it["unit_code"] == cart_item.unit_code), None)
        attrs = sku.attrs or {}
        image_url = None
        for key in ("image", "cover", "cover_url"):
            value = attrs.get(key)
            if isinstance(value, str) and value:
                image_url = value
                break
        if image_url is None:
            for key in ("images", "pics", "gallery"):
                value = attrs.get(key)
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, str) and first:
                        image_url = first
                        break

        out.append(
            ShoppingCartItemOut(
                sku_id=sku.id,
                product_id=product.id,
                product_code=product.product_code,
                product_name=product.name,
                category=product.category,
                subcategory=product.subcategory,
                sku_name=sku.sku_name,
                sku_code=sku.sku_code,
                unit_code=cart_item.unit_code,
                unit_name=selected_unit["unit_name"] if selected_unit else cart_item.unit_code,
                quantity=cart_item.quantity,
                unit_price=str(sku.retail_price),
                image_url=image_url,
                attrs=attrs,
                min_wholesale_base_qty=sku.min_wholesale_base_qty,
                on_hand_base_qty=inventory.on_hand_base_qty,
                reserved_base_qty=inventory.reserved_base_qty,
                sellable_stock=inventory.on_hand_base_qty - inventory.reserved_base_qty,
                conversions=convs,
            )
        )
    return out


@router.get("", response_model=list[UserAdminOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    role: UserRole | None = Query(default=None),
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[UserAdminOut]:
    stmt = select(User).options(selectinload(User.profile)).order_by(desc(User.id))
    if role:
        stmt = stmt.where(User.role == role)
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.join(CustomerProfile, CustomerProfile.user_id == User.id, isouter=True).where(
            User.username.ilike(like_kw)
            | CustomerProfile.phone.ilike(like_kw)
            | CustomerProfile.wechat_openid.ilike(like_kw)
            | CustomerProfile.display_name.ilike(like_kw)
        )

    users = (await db.scalars(stmt)).all()
    return [_serialize_user(item) for item in users]


@router.patch("/role", response_model=UserAdminOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def assign_user_role(
    payload: UserRoleAssignIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminOut:
    filters = []
    if payload.user_id is not None:
        filters.append(User.id == payload.user_id)
    if payload.phone:
        filters.append(CustomerProfile.phone == normalize_phone(payload.phone))
    if payload.wechat_openid:
        filters.append(CustomerProfile.wechat_openid == payload.wechat_openid.strip())
    if not filters:
        raise bad_request("user_id or phone or wechat_openid is required")

    stmt = (
        select(User)
        .outerjoin(CustomerProfile, CustomerProfile.user_id == User.id)
        .options(selectinload(User.profile))
        .where(or_(*filters))
        .limit(1)
    )
    user = await db.scalar(stmt)
    if not user:
        raise not_found("user not found")
    if payload.role == UserRole.ADMIN:
        raise bad_request("role assignment to admin is not supported here")

    user.role = payload.role
    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    if payload.role == UserRole.WHOLESALE:
        user.profile.is_verified_wholesale = True
    elif payload.role in {UserRole.RETAIL, UserRole.EMPLOYEE} and payload.is_verified_wholesale is None:
        user.profile.is_verified_wholesale = False
    elif payload.is_verified_wholesale is not None:
        user.profile.is_verified_wholesale = payload.is_verified_wholesale

    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.post("/customers", response_model=UserAdminOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_customer(
    payload: CustomerCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminOut:
    if payload.role == UserRole.ADMIN:
        raise bad_request("customer role cannot be admin")
    exists = await db.scalar(select(User.id).where(User.username == payload.username))
    if exists:
        raise bad_request("username already exists")
    normalized_phone = normalize_phone(payload.phone) if payload.phone else None
    if normalized_phone:
        phone_exists = await db.scalar(select(CustomerProfile.id).where(CustomerProfile.phone == normalized_phone))
        if phone_exists:
            raise bad_request("phone already exists")

    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    db.add(
        CustomerProfile(
            user_id=user.id,
            display_name=payload.display_name,
            phone=normalized_phone,
            company_name=payload.company_name,
            contact_name=payload.contact_name,
            address=payload.address,
            note=payload.note,
            is_verified_wholesale=payload.is_verified_wholesale,
        )
    )
    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.patch("/{user_id}/status", response_model=UserAdminOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminOut:
    user = await db.get(User, user_id)
    if not user:
        raise not_found("user not found")

    user.is_active = payload.is_active
    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.patch("/{user_id}/profile", response_model=UserAdminOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_customer_profile(
    user_id: int,
    payload: CustomerProfileUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")

    profile = user.profile
    if not profile:
        profile = CustomerProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

    update_data = payload.model_dump(exclude_unset=True)
    if "phone" in update_data and update_data["phone"]:
        normalized_phone = normalize_phone(update_data["phone"])
        phone_exists = await db.scalar(
            select(CustomerProfile.id).where(CustomerProfile.phone == normalized_phone, CustomerProfile.user_id != user.id)
        )
        if phone_exists:
            raise bad_request("phone already exists")
        update_data["phone"] = normalized_phone
    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.get("/me/profile", response_model=UserAdminOut)
async def my_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserAdminOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.patch("/me/profile", response_model=UserAdminOut)
@router.put("/me/profile", response_model=UserAdminOut)
async def update_my_profile(
    payload: CustomerSelfProfileUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserAdminOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user.profile, key, value)
    await db.commit()
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_user(user)


@router.patch("/me/password")
async def update_my_password(
    payload: CustomerSelfPasswordUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    if not verify_password(payload.current_password, user.password_hash):
        raise bad_request("current password is incorrect")
    if payload.current_password == payload.new_password:
        raise bad_request("new password must be different from current password")
    user.password_hash = get_password_hash(payload.new_password)
    await db.commit()
    return {"id": user.id, "updated": True}


@router.get("/me/addresses", response_model=list[CustomerAddressOut])
async def list_my_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerAddressOut]:
    rows = (
        await db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc())
        )
    ).all()
    return [_serialize_address(item) for item in rows]


@router.post("/me/addresses", response_model=CustomerAddressOut)
async def create_my_address(
    payload: CustomerAddressCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    item = CustomerAddress(
        user_id=current_user.id,
        recipient=payload.recipient.strip(),
        phone=normalize_phone(payload.phone),
        province=payload.province.strip(),
        city=payload.city.strip(),
        district=payload.district.strip(),
        detail=payload.detail.strip(),
        is_default=payload.is_default,
    )
    db.add(item)
    await db.flush()
    await _ensure_single_default_address(db, current_user.id, item.id if item.is_default else None)
    await db.commit()
    await db.refresh(item)
    return _serialize_address(item)


@router.patch("/me/addresses/{address_id}", response_model=CustomerAddressOut)
@router.put("/me/addresses/{address_id}", response_model=CustomerAddressOut)
async def update_my_address(
    address_id: int,
    payload: CustomerAddressUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    item = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not item:
        raise not_found("address not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "phone" and value:
            value = normalize_phone(value)
        if isinstance(value, str):
            value = value.strip()
        setattr(item, key, value)
    await _ensure_single_default_address(db, current_user.id, item.id if item.is_default else None)
    await db.commit()
    await db.refresh(item)
    return _serialize_address(item)


@router.delete("/me/addresses/{address_id}")
async def delete_my_address(
    address_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    item = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not item:
        raise not_found("address not found")
    await db.delete(item)
    await db.flush()
    await _ensure_single_default_address(db, current_user.id)
    await db.commit()
    return {"deleted": True, "id": address_id}


@router.post("/me/addresses/{address_id}/default")
async def set_my_address_default(
    address_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    item = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not item:
        raise not_found("address not found")
    await _ensure_single_default_address(db, current_user.id, address_id)
    await db.commit()
    return {"id": address_id, "is_default": True}


@router.get("/me/cart", response_model=list[ShoppingCartItemOut])
async def list_my_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ShoppingCartItemOut]:
    return await _serialize_cart_items(db, current_user.id)


@router.put("/me/cart", response_model=list[ShoppingCartItemOut])
async def sync_my_cart(
    payload: ShoppingCartSyncIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ShoppingCartItemOut]:
    await db.execute(delete(ShoppingCartItem).where(ShoppingCartItem.user_id == current_user.id))
    if payload.items:
        for item in payload.items:
            db.add(
                ShoppingCartItem(
                    user_id=current_user.id,
                    sku_id=item.sku_id,
                    unit_code=item.unit_code.strip(),
                    quantity=item.quantity,
                )
            )
    await db.commit()
    return await _serialize_cart_items(db, current_user.id)


def _serialize_wholesale_application(item: WholesaleApplication, username: str | None = None) -> WholesaleApplicationOut:
    return WholesaleApplicationOut(
        id=item.id,
        user_id=item.user_id,
        username=username,
        status=item.status,
        company_name=item.company_name,
        contact_name=item.contact_name,
        contact_phone=item.contact_phone,
        reason=item.reason,
        review_note=item.review_note,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at.isoformat() if item.reviewed_at else None,
        created_at=item.created_at.isoformat(),
    )


@router.post("/wholesale-applications", response_model=WholesaleApplicationOut)
async def create_wholesale_application(
    payload: WholesaleApplicationCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WholesaleApplicationOut:
    if current_user.role == UserRole.WHOLESALE:
        raise bad_request("user is already wholesale")
    active = await db.scalar(
        select(WholesaleApplication.id).where(
            WholesaleApplication.user_id == current_user.id,
            WholesaleApplication.status == "pending",
        )
    )
    if active:
        raise bad_request("pending wholesale application already exists")

    item = WholesaleApplication(
        user_id=current_user.id,
        status="pending",
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        reason=payload.reason,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize_wholesale_application(item, username=current_user.username)


@router.get("/wholesale-applications", response_model=list[WholesaleApplicationOut])
async def list_wholesale_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
) -> list[WholesaleApplicationOut]:
    stmt = select(WholesaleApplication, User.username).join(User, User.id == WholesaleApplication.user_id)
    if status:
        stmt = stmt.where(WholesaleApplication.status == status)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(WholesaleApplication.user_id == current_user.id)
    stmt = stmt.order_by(desc(WholesaleApplication.id)).limit(200)
    rows = (await db.execute(stmt)).all()
    return [_serialize_wholesale_application(item, username=username) for item, username in rows]


@router.patch(
    "/wholesale-applications/{application_id}/review",
    response_model=WholesaleApplicationOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def review_wholesale_application(
    application_id: int,
    payload: WholesaleApplicationReviewIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WholesaleApplicationOut:
    item = await db.get(WholesaleApplication, application_id)
    if not item:
        raise not_found("wholesale application not found")
    if item.status != "pending":
        raise bad_request("application already reviewed")

    item.status = payload.status
    item.review_note = payload.review_note
    item.reviewed_by = current_user.id
    from datetime import UTC, datetime

    item.reviewed_at = datetime.now(UTC)

    user = await db.get(User, item.user_id)
    if not user:
        raise not_found("applicant user not found")
    if payload.status == "approved":
        user.role = UserRole.WHOLESALE
        profile = await db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
        if not profile:
            profile = CustomerProfile(user_id=user.id)
            db.add(profile)
        profile.is_verified_wholesale = True
        if item.company_name and not profile.company_name:
            profile.company_name = item.company_name
        if item.contact_name and not profile.contact_name:
            profile.contact_name = item.contact_name
        if item.contact_phone and not profile.phone:
            profile.phone = item.contact_phone

    await db.commit()
    await db.refresh(item)
    return _serialize_wholesale_application(item, username=user.username)
