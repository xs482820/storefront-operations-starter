from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import bad_request, forbidden, not_found, unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.aftersale import AfterSaleRequest
from app.models.customer_runtime import (
    CustomerAddress,
    CustomerCartItem,
    CustomerNotification,
    CustomerProductFavorite,
    CustomerSearchHistory,
)
from app.models.enums import (
    AfterSaleStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    SKUType,
    UserRole,
    WholesaleApplicationStatus,
)
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.product import Product, ProductSKU
from app.models.storefront import StorefrontMarqueeNotice
from app.models.user import User, WholesaleApplication
from app.schemas.customer import (
    CustomerAfterSaleCreateIn,
    CustomerAfterSaleOut,
    CustomerAddressIn,
    CustomerAddressOut,
    CustomerCartBatchSyncIn,
    CustomerCartBatchSyncIssueOut,
    CustomerCartBatchSyncOut,
    CustomerCartItemOut,
    CustomerCartUpsertIn,
    CustomerCategoryOut,
    CustomerCheckoutPreviewIn,
    CustomerCheckoutPreviewItemOut,
    CustomerCheckoutPreviewOut,
    CustomerFavoriteOut,
    CustomerMeOut,
    CustomerMeUpdateIn,
    CustomerNotificationOut,
    CustomerOrderCreateIn,
    CustomerOrderItemOut,
    CustomerOrderOut,
    CustomerProductOut,
    CustomerProductSKUOut,
    CustomerSearchHistoryIn,
    CustomerSearchHistoryOut,
    StorefrontMarqueeNoticeOut,
    WechatPayCreateOut,
    WholesaleApplicationCreateIn,
    WholesaleApplicationOut,
)
from app.services.storefront_config import load_storefront_config
from app.services.orders import cancel_order as cancel_customer_order
from app.services.orders import delete_order as delete_customer_order
from app.services.orders import complete_order as complete_customer_order
from app.services.orders import create_customer_order
from app.services.events import write_business_event
from app.services.notifications import create_customer_notification
from app.services.ops_jobs import cancel_order_if_expired
from app.services.shipping import calculate_shipping_fee, get_shipping_threshold
from app.services.wechat_pay import build_jsapi_pay_params, create_jsapi_transaction

router = APIRouter(prefix="/customer", tags=["customer"])
settings = get_settings()
UPLOAD_ROOT = Path("/app/uploads/customer")
UPLOAD_ROOT_FALLBACK = Path("uploads/customer")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def _can_use_wholesale_scope(user: User) -> bool:
    return user.role in {UserRole.WHOLESALE, UserRole.EMPLOYEE}


def _extract_token_from_request(request: Request) -> str | None:
    for header_name in ("authorization", "token", "x-token"):
        raw = request.headers.get(header_name)
        if not raw:
            continue
        value = raw.strip()
        if not value:
            continue
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        if value:
            return value
    return None


async def _get_optional_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    token = _extract_token_from_request(request)
    if not token:
        return None
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
    if user.role in {UserRole.RETAIL, UserRole.WHOLESALE} and user.is_blacklisted:
        raise forbidden("Account is blacklisted")
    return user


def _parse_image_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str) and item.strip()]
    except json.JSONDecodeError:
        return []
    return []


async def _load_favorite_product_ids(
    db: AsyncSession,
    current_user: User | None,
    product_ids: list[int],
) -> set[int]:
    if not current_user or not product_ids:
        return set()
    rows = (
        await db.scalars(
            select(CustomerProductFavorite.product_id).where(
                CustomerProductFavorite.user_id == current_user.id,
                CustomerProductFavorite.product_id.in_(product_ids),
            )
        )
    ).all()
    return set(rows)


def _serialize_customer_product(
    product: Product,
    skus: list[CustomerProductSKUOut],
    *,
    is_favorited: bool = False,
) -> CustomerProductOut:
    return CustomerProductOut(
        product_id=product.id,
        product_code=product.product_code,
        name=product.name,
        model_name=product.model_name,
        brand=product.brand,
        category=product.category,
        description=product.description,
        image_urls=_parse_image_urls(product.image_urls),
        spec_dim_1_name=product.spec_dim_1_name,
        spec_dim_2_name=product.spec_dim_2_name,
        skus=skus,
        is_favorited=is_favorited,
    )


def _normalize_shipping_channel(value: str | None) -> str:
    return "pickup" if value == "pickup" else "delivery"


def _resolve_effective_role_and_mode(current_user: User, pricing_mode: str | None) -> tuple[UserRole, str]:
    requested_pricing_mode = pricing_mode or (
        "wholesale" if current_user.role == UserRole.WHOLESALE else "retail"
    )
    effective_role = UserRole.WHOLESALE if requested_pricing_mode == "wholesale" else UserRole.RETAIL
    if effective_role == UserRole.WHOLESALE and current_user.role not in {UserRole.WHOLESALE, UserRole.EMPLOYEE}:
        raise bad_request("wholesale purchase is only available for wholesale users")
    return effective_role, requested_pricing_mode


def _resolve_expected_sku_type(effective_role: UserRole) -> SKUType:
    return SKUType.WHOLESALE if effective_role == UserRole.WHOLESALE else SKUType.RETAIL


async def _resolve_role_sku(db: AsyncSession, sku: ProductSKU, expected_sku_type: SKUType) -> ProductSKU:
    """Map an old cart SKU to the active scope without changing the current role's pricing."""
    if sku.sku_type == expected_sku_type:
        return sku
    replacement = await db.scalar(
        select(ProductSKU)
        .options(selectinload(ProductSKU.product))
        .where(
            ProductSKU.product_id == sku.product_id,
            ProductSKU.sku_type == expected_sku_type,
            ProductSKU.spec_value_1 == sku.spec_value_1,
            ProductSKU.spec_value_2 == sku.spec_value_2,
            ProductSKU.is_active.is_(True),
        )
    )
    # ponytail: legacy products can have only one SKU type; prices are still selected from the active role below.
    return replacement or sku


def _serialize_cart_item_with_sku(row: CustomerCartItem, sku: ProductSKU, current_user: User) -> CustomerCartItemOut:
    return CustomerCartItemOut(
        product_id=sku.product_id,
        sku_id=sku.id,
        sku_type=sku.sku_type.value,
        product_name=sku.product.name if sku.product else sku.sku_code,
        sku_code=sku.sku_code,
        spec_value_1=sku.spec_value_1,
        spec_value_2=sku.spec_value_2,
        quantity=row.quantity,
        online_stock=sku.online_stock,
        retail_price=Decimal(sku.retail_price),
        wholesale_price=Decimal(sku.wholesale_price) if _can_use_wholesale_scope(current_user) else None,
        min_sale_qty=sku.min_sale_qty,
        min_wholesale_qty=sku.min_wholesale_qty,
        selected=row.selected,
        delisted=not bool(sku.is_active and sku.product and sku.product.is_active),
        product_image_url=_parse_image_urls(sku.product.image_urls)[0] if sku.product and _parse_image_urls(sku.product.image_urls) else None,
    )


async def _load_customer_cart_items(db: AsyncSession, current_user: User) -> list[CustomerCartItemOut]:
    rows = (
        await db.scalars(
            select(CustomerCartItem)
            .where(CustomerCartItem.user_id == current_user.id)
            .order_by(desc(CustomerCartItem.updated_at))
            .limit(200)
        )
    ).all()
    if not rows:
        return []

    sku_ids = [row.sku_id for row in rows]
    skus = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id.in_(sku_ids))
        )
    ).all()
    sku_map = {sku.id: sku for sku in skus}

    result: list[CustomerCartItemOut] = []
    for row in rows:
        sku = sku_map.get(row.sku_id)
        if not sku:
            continue
        result.append(_serialize_cart_item_with_sku(row, sku, current_user))
    return result


async def _build_checkout_preview(
    *,
    db: AsyncSession,
    current_user: User,
    payload: CustomerCheckoutPreviewIn,
) -> CustomerCheckoutPreviewOut:
    effective_role, resolved_pricing_mode = _resolve_effective_role_and_mode(current_user, payload.pricing_mode)
    if payload.payment_method == PaymentMethod.OFFLINE_TRANSFER and effective_role != UserRole.WHOLESALE:
        raise bad_request("offline_transfer is only available for wholesale users")

    expected_sku_type = _resolve_expected_sku_type(effective_role)
    preview_items: list[CustomerCheckoutPreviewItemOut] = []
    issues: list[str] = []
    merchandise_amount = Decimal("0.00")

    for item in payload.items:
        sku = await db.scalar(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id == item.sku_id, ProductSKU.is_active.is_(True))
        )
        if not sku or not sku.product or not sku.product.is_active:
            raise not_found("sku not found")
        sku = await _resolve_role_sku(db, sku, expected_sku_type)
        if effective_role == UserRole.RETAIL and not sku.product.supports_retail:
            raise bad_request("product is not available for retail")
        if effective_role == UserRole.WHOLESALE and not sku.product.supports_wholesale:
            raise bad_request("product is not available for wholesale")

        min_required_qty = sku.min_wholesale_qty if effective_role == UserRole.WHOLESALE else sku.min_sale_qty
        if item.quantity < min_required_qty:
            issues.append(f"{sku.product.name} 购买数量不能少于 {min_required_qty}")
        if sku.online_stock < item.quantity:
            issues.append(f"{sku.product.name} 库存不足，当前仅剩 {sku.online_stock}")

        unit_price = Decimal(sku.wholesale_price) if effective_role == UserRole.WHOLESALE else Decimal(sku.retail_price)
        line_amount = unit_price * item.quantity
        merchandise_amount += line_amount
        image_urls = _parse_image_urls(sku.product.image_urls)
        preview_items.append(
            CustomerCheckoutPreviewItemOut(
                product_id=sku.product_id,
                sku_id=sku.id,
                product_name=sku.product.name,
                sku_code=sku.sku_code,
                sku_type=sku.sku_type.value,
                spec_value_1=sku.spec_value_1,
                spec_value_2=sku.spec_value_2,
                quantity=item.quantity,
                unit_price=unit_price,
                line_amount=line_amount,
                online_stock=sku.online_stock,
                min_required_qty=min_required_qty,
                product_image_url=image_urls[0] if image_urls else None,
            )
        )

    shipping_channel = _normalize_shipping_channel(payload.shipping_channel)
    free_shipping_threshold = get_shipping_threshold(role=effective_role)
    shortfall_to_free_shipping = Decimal("0.00")
    if shipping_channel != "pickup" and free_shipping_threshold > Decimal("0.00") and merchandise_amount < free_shipping_threshold:
        shortfall_to_free_shipping = free_shipping_threshold - merchandise_amount

    shipping_fee = calculate_shipping_fee(
        role=effective_role,
        merchandise_amount=merchandise_amount,
        shipping_channel=shipping_channel,
    )
    payable_amount = merchandise_amount + shipping_fee
    if effective_role == UserRole.WHOLESALE and payload.payment_method == PaymentMethod.OFFLINE_TRANSFER:
        payable_amount = merchandise_amount

    return CustomerCheckoutPreviewOut(
        buyer_role=effective_role.value,
        pricing_mode=resolved_pricing_mode,
        shipping_channel=shipping_channel,
        payment_method=payload.payment_method.value,
        merchandise_amount=merchandise_amount,
        shipping_fee=shipping_fee,
        payable_amount=payable_amount,
        free_shipping_threshold=free_shipping_threshold,
        shortfall_to_free_shipping=shortfall_to_free_shipping,
        can_submit=not issues,
        issues=issues,
        items=preview_items,
    )


def _serialize_me(user: User) -> CustomerMeOut:
    profile = user.profile
    return CustomerMeOut(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        display_name=profile.display_name if profile else None,
        phone=profile.phone if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        company_name=profile.company_name if profile else None,
        store_name=profile.store_name if profile else None,
        contact_name=profile.contact_name if profile else None,
        address=profile.address if profile else None,
        business_license_url=profile.business_license_url if profile else None,
        is_verified_wholesale=bool(profile.is_verified_wholesale) if profile else False,
        wechat_bound=bool(profile.wechat_openid) if profile else False,
        employee_mode=(
            profile.employee_mode
            if profile and profile.employee_mode in {"shopping", "workbench"}
            else "shopping"
        ),
        miniapp_notification_enabled=bool(profile.miniapp_notification_enabled) if profile else False,
        miniapp_notification_event_keys=list(profile.miniapp_notification_event_keys or []) if profile else [],
        miniapp_notification_updated_at=(
            profile.miniapp_notification_updated_at.isoformat()
            if profile and profile.miniapp_notification_updated_at
            else None
        ),
    )

def _resolve_application_effective_status(user: User, row: WholesaleApplication) -> str:
    if row.status == WholesaleApplicationStatus.PENDING:
        return "pending"
    if row.status == WholesaleApplicationStatus.REJECTED:
        return "rejected"
    if user.role in {UserRole.WHOLESALE, UserRole.EMPLOYEE}:
        return "approved"
    return "revoked"


async def _load_order_sku_map(db: AsyncSession, items: list[OrderItem]) -> dict[int, ProductSKU]:
    sku_ids = [item.sku_id for item in items]
    if not sku_ids:
        return {}
    rows = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id.in_(sku_ids))
        )
    ).all()
    return {row.id: row for row in rows}


def _serialize_order(order: Order, items: list[OrderItem], sku_map: dict[int, ProductSKU] | None = None) -> CustomerOrderOut:
    return CustomerOrderOut(
        order_id=order.id,
        order_no=order.order_no,
        status=order.status.value,
        buyer_role=order.buyer_role.value,
        original_amount=Decimal(order.original_amount),
        shipping_fee=Decimal(order.shipping_fee),
        payable_amount=Decimal(order.payable_amount),
        payment_method=order.payment_method.value,
        shipping_mode=order.shipping_mode.value if order.shipping_mode else None,
        shipping_proof_url=order.shipping_proof_url,
        shipping_recipient=order.shipping_recipient,
        shipping_phone=order.shipping_phone,
        shipping_address=order.shipping_address,
        note=order.customer_note or order.note,
        cancellation_reason=order.cancellation_reason,
        cancellation_source=order.cancellation_source,
        termination_reason=order.termination_reason,
        termination_disposition=order.termination_disposition,
        created_at=order.created_at.isoformat(),
        paid_at=order.paid_at.isoformat() if order.paid_at else None,
        shipped_at=order.shipped_at.isoformat() if order.shipped_at else None,
        delivery_signed_at=order.delivery_signed_at.isoformat() if order.delivery_signed_at else None,
        completed_at=order.completed_at.isoformat() if order.completed_at else None,
        canceled_at=order.canceled_at.isoformat() if order.canceled_at else None,
        terminated_at=order.terminated_at.isoformat() if order.terminated_at else None,
        items=[
            CustomerOrderItemOut(
                product_id=sku_map[item.sku_id].product_id if sku_map and item.sku_id in sku_map else None,
                sku_id=item.sku_id,
                product_name=item.product_name_snapshot,
                sku_code=item.sku_code_snapshot,
                sku_type=item.sku_type_snapshot,
                spec_value_1=item.spec_value_1_snapshot,
                spec_value_2=item.spec_value_2_snapshot,
                product_image_url=(
                    _parse_image_urls(sku_map[item.sku_id].product.image_urls)[0]
                    if sku_map
                    and item.sku_id in sku_map
                    and sku_map[item.sku_id].product
                    and _parse_image_urls(sku_map[item.sku_id].product.image_urls)
                    else None
                ),
                quantity=item.quantity,
                unit_price=Decimal(item.unit_price),
                line_amount=Decimal(item.line_amount),
            )
            for item in items
        ],
        # 计算字段逻辑
        can_cancel=order.status == OrderStatus.PENDING_PAYMENT,
        can_confirm_receipt=order.status == OrderStatus.SHIPPED,
        can_aftersale=order.status in {OrderStatus.SHIPPED, OrderStatus.COMPLETED},
        can_delete=order.status in {OrderStatus.CANCELED, OrderStatus.COMPLETED},
    )


def _serialize_address(item: CustomerAddress) -> CustomerAddressOut:
    return CustomerAddressOut(
        id=item.id,
        contact_name=item.contact_name,
        phone=item.phone,
        region=item.region,
        detail=item.detail,
        tag=item.tag,
        is_default=item.is_default,
        created_at=item.created_at.isoformat(),
    )


@router.get("/me", response_model=CustomerMeOut)
async def get_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerMeOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    return _serialize_me(user)


@router.patch("/me", response_model=CustomerMeOut)
async def update_me(
    payload: CustomerMeUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerMeOut:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    if not user.profile:
        raise bad_request("user profile missing")
    update_data = payload.model_dump(exclude_unset=True)
    employee_mode = update_data.get("employee_mode")
    if employee_mode is not None and user.role != UserRole.EMPLOYEE:
        update_data.pop("employee_mode", None)
    notification_enabled = update_data.get("miniapp_notification_enabled")
    notification_event_keys = update_data.get("miniapp_notification_event_keys")
    for key, value in update_data.items():
        setattr(user.profile, key, value)
    if "miniapp_notification_enabled" in update_data or "miniapp_notification_event_keys" in update_data:
        user.profile.miniapp_notification_enabled = bool(notification_enabled)
        user.profile.miniapp_notification_event_keys = list(notification_event_keys or [])
        user.profile.miniapp_notification_updated_at = datetime.now(UTC)
    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="customer.profile.updated",
        action_label="客户资料更新",
        source="customer",
        actor=current_user,
        after_data=update_data,
    )
    await db.commit()
    await db.refresh(user.profile)
    return _serialize_me(user)


def _serialize_marquee_notice(row: StorefrontMarqueeNotice) -> StorefrontMarqueeNoticeOut:
    return StorefrontMarqueeNoticeOut(
        id=row.id,
        title=row.title,
        body=row.body,
        action_label=row.action_label,
        action_type=row.action_type,
        action_value=row.action_value,
    )


async def _list_active_marquee_notices(db: AsyncSession) -> list[StorefrontMarqueeNoticeOut]:
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(StorefrontMarqueeNotice)
            .where(StorefrontMarqueeNotice.is_active.is_(True))
            .where(or_(StorefrontMarqueeNotice.starts_at.is_(None), StorefrontMarqueeNotice.starts_at <= now))
            .where(or_(StorefrontMarqueeNotice.ends_at.is_(None), StorefrontMarqueeNotice.ends_at > now))
            .order_by(StorefrontMarqueeNotice.sort_order.asc(), StorefrontMarqueeNotice.id.asc())
            .limit(20)
        )
    ).scalars().all()
    return [_serialize_marquee_notice(row) for row in rows]


@router.get("/storefront-config")
async def get_storefront_config(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    config = load_storefront_config()
    config["marquee_notices"] = [item.model_dump() for item in await _list_active_marquee_notices(db)]
    return config


@router.get("/marquee-notices", response_model=list[StorefrontMarqueeNoticeOut])
async def list_marquee_notices(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StorefrontMarqueeNoticeOut]:
    return await _list_active_marquee_notices(db)


@router.get("/categories", response_model=list[CustomerCategoryOut])
async def list_customer_categories(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CustomerCategoryOut]:
    current_user = await _get_optional_current_user(request, db)
    can_wholesale = _can_use_wholesale_scope(current_user) if current_user else False
    stmt = select(Product.category, func.count(Product.id)).where(Product.is_active.is_(True))
    if can_wholesale:
        stmt = stmt.where(Product.supports_wholesale.is_(True))
    else:
        stmt = stmt.where(Product.supports_retail.is_(True))
    stmt = stmt.where(Product.category.is_not(None)).group_by(Product.category).order_by(Product.category.asc())
    rows = (await db.execute(stmt)).all()
    return [
        CustomerCategoryOut(
            code=(str(category).strip().lower().replace(" ", "-") or "uncategorized"),
            name=str(category).strip(),
            product_count=int(product_count or 0),
        )
        for category, product_count in rows
        if str(category or "").strip()
    ]


@router.post("/upload-image")
async def upload_customer_image(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> dict:
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise bad_request("unsupported image type")

    content = await file.read()
    if not content:
        raise bad_request("empty file")
    if len(content) > MAX_IMAGE_SIZE:
        raise bad_request("image size exceeds 10MB")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    saved_name = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex}{ext}"
    saved_path = UPLOAD_ROOT / saved_name
    saved_path.write_bytes(content)
    base_url = settings.PUBLIC_ASSET_BASE_URL.rstrip("/")
    return {
        "url": f"{base_url}/api/v1/customer/uploads/{saved_name}",
        "name": filename,
        "size": len(content),
    }


@router.get("/uploads/{file_name}")
async def get_uploaded_customer_image(file_name: str) -> FileResponse:
    if "/" in file_name or "\\" in file_name:
        raise not_found("file not found")
    roots = [UPLOAD_ROOT, UPLOAD_ROOT_FALLBACK]
    for root in roots:
        try:
            file_path = (root / file_name).resolve()
            if file_path.exists() and file_path.parent == root.resolve():
                return FileResponse(file_path)
        except Exception:
            continue
    raise not_found("file not found")


@router.get("/products", response_model=list[CustomerProductOut])
async def list_products(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[CustomerProductOut]:
    current_user = await _get_optional_current_user(request, db)
    can_wholesale = _can_use_wholesale_scope(current_user) if current_user else False
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    stmt = (
        select(Product)
        .options(selectinload(Product.skus))
        .where(Product.is_active.is_(True))
        .order_by(desc(Product.id))
    )
    if sku_type == SKUType.RETAIL:
        stmt = stmt.where(Product.supports_retail.is_(True))
    else:
        stmt = stmt.where(Product.supports_wholesale.is_(True))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.where(Product.name.ilike(like_kw) | Product.model_name.ilike(like_kw))

    products = (await db.scalars(stmt)).all()
    favorite_product_ids = await _load_favorite_product_ids(db, current_user, [product.id for product in products])
    result: list[CustomerProductOut] = []
    for product in products:
        skus = [
            CustomerProductSKUOut(
                sku_id=sku.id,
                sku_code=sku.sku_code,
                sku_type=sku.sku_type.value,
                spec_value_1=sku.spec_value_1,
                spec_value_2=sku.spec_value_2,
                sku_label=sku.sku_label,
                online_stock=sku.online_stock,
                retail_price=Decimal(sku.retail_price),
                wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
                min_sale_qty=sku.min_sale_qty,
                min_wholesale_qty=sku.min_wholesale_qty,
                is_mixed_pack=sku.is_mixed_pack,
                mixed_pack_note=sku.mixed_pack_note,
            )
            for sku in product.skus
            if sku.is_active and sku.sku_type == sku_type
        ]
        if not skus:
            continue
        result.append(_serialize_customer_product(product, skus, is_favorited=product.id in favorite_product_ids))
    return result


@router.get("/products/{product_id}", response_model=CustomerProductOut)
async def get_product_detail(
    product_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerProductOut:
    current_user = await _get_optional_current_user(request, db)
    can_wholesale = _can_use_wholesale_scope(current_user) if current_user else False
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    product = await db.scalar(
        select(Product).options(selectinload(Product.skus)).where(Product.id == product_id, Product.is_active.is_(True))
    )
    if not product:
        raise not_found("product not found")
    if sku_type == SKUType.RETAIL and not product.supports_retail:
        raise not_found("product not found")
    if sku_type == SKUType.WHOLESALE and not product.supports_wholesale:
        raise not_found("product not found")

    skus = [
        CustomerProductSKUOut(
            sku_id=sku.id,
            sku_code=sku.sku_code,
            sku_type=sku.sku_type.value,
            spec_value_1=sku.spec_value_1,
            spec_value_2=sku.spec_value_2,
            sku_label=sku.sku_label,
            online_stock=sku.online_stock,
            retail_price=Decimal(sku.retail_price),
            wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
            min_sale_qty=sku.min_sale_qty,
            min_wholesale_qty=sku.min_wholesale_qty,
            is_mixed_pack=sku.is_mixed_pack,
            mixed_pack_note=sku.mixed_pack_note,
        )
        for sku in product.skus
        if sku.is_active and sku.sku_type == sku_type
    ]
    if not skus:
        raise not_found("product not found")

    favorite_product_ids = await _load_favorite_product_ids(db, current_user, [product.id])
    return _serialize_customer_product(product, skus, is_favorited=product.id in favorite_product_ids)


@router.get("/favorites", response_model=list[CustomerFavoriteOut])
async def list_favorites(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerFavoriteOut]:
    can_wholesale = _can_use_wholesale_scope(current_user)
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    rows = (
        await db.scalars(
            select(CustomerProductFavorite)
            .where(CustomerProductFavorite.user_id == current_user.id)
            .order_by(desc(CustomerProductFavorite.id))
            .limit(200)
        )
    ).all()
    if not rows:
        return []

    products = (
        await db.scalars(
            select(Product)
            .options(selectinload(Product.skus))
            .where(
                Product.id.in_([row.product_id for row in rows]),
                Product.is_active.is_(True),
            )
        )
    ).all()
    product_map = {product.id: product for product in products}
    result: list[CustomerFavoriteOut] = []
    for row in rows:
        product = product_map.get(row.product_id)
        if not product:
            continue
        if sku_type == SKUType.RETAIL and not product.supports_retail:
            continue
        if sku_type == SKUType.WHOLESALE and not product.supports_wholesale:
            continue
        skus = [
            CustomerProductSKUOut(
                sku_id=sku.id,
                sku_code=sku.sku_code,
                sku_type=sku.sku_type.value,
                spec_value_1=sku.spec_value_1,
                spec_value_2=sku.spec_value_2,
                sku_label=sku.sku_label,
                online_stock=sku.online_stock,
                retail_price=Decimal(sku.retail_price),
                wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
                min_sale_qty=sku.min_sale_qty,
                min_wholesale_qty=sku.min_wholesale_qty,
                is_mixed_pack=sku.is_mixed_pack,
                mixed_pack_note=sku.mixed_pack_note,
            )
            for sku in product.skus
            if sku.is_active and sku.sku_type == sku_type
        ]
        if not skus:
            continue
        result.append(
            CustomerFavoriteOut(
                id=row.id,
                product_id=row.product_id,
                created_at=row.created_at.isoformat(),
                product=_serialize_customer_product(product, skus, is_favorited=True),
            )
        )
    return result


@router.post("/favorites/{product_id}", response_model=CustomerFavoriteOut)
async def add_favorite(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerFavoriteOut:
    can_wholesale = _can_use_wholesale_scope(current_user)
    sku_type = SKUType.WHOLESALE if can_wholesale else SKUType.RETAIL
    product = await db.scalar(
        select(Product).options(selectinload(Product.skus)).where(Product.id == product_id, Product.is_active.is_(True))
    )
    if not product:
        raise not_found("product not found")
    if sku_type == SKUType.RETAIL and not product.supports_retail:
        raise not_found("product not found")
    if sku_type == SKUType.WHOLESALE and not product.supports_wholesale:
        raise not_found("product not found")

    row = await db.scalar(
        select(CustomerProductFavorite).where(
            CustomerProductFavorite.user_id == current_user.id,
            CustomerProductFavorite.product_id == product_id,
        )
    )
    if not row:
        row = CustomerProductFavorite(user_id=current_user.id, product_id=product_id)
        db.add(row)
        await db.flush()
    skus = [
        CustomerProductSKUOut(
            sku_id=sku.id,
            sku_code=sku.sku_code,
            sku_type=sku.sku_type.value,
            spec_value_1=sku.spec_value_1,
            spec_value_2=sku.spec_value_2,
            sku_label=sku.sku_label,
            online_stock=sku.online_stock,
            retail_price=Decimal(sku.retail_price),
            wholesale_price=Decimal(sku.wholesale_price) if can_wholesale else None,
            min_sale_qty=sku.min_sale_qty,
            min_wholesale_qty=sku.min_wholesale_qty,
            is_mixed_pack=sku.is_mixed_pack,
            mixed_pack_note=sku.mixed_pack_note,
        )
        for sku in product.skus
        if sku.is_active and sku.sku_type == sku_type
    ]
    if not skus:
        raise not_found("product not found")
    await db.commit()
    await db.refresh(row)
    return CustomerFavoriteOut(
        id=row.id,
        product_id=row.product_id,
        created_at=row.created_at.isoformat(),
        product=_serialize_customer_product(product, skus, is_favorited=True),
    )


@router.delete("/favorites/{product_id}")
async def remove_favorite(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerProductFavorite).where(
            CustomerProductFavorite.user_id == current_user.id,
            CustomerProductFavorite.product_id == product_id,
        )
    )
    if not row:
        return {"removed": 0}
    await db.delete(row)
    await db.commit()
    return {"removed": 1}


@router.post("/checkout/preview", response_model=CustomerCheckoutPreviewOut)
async def checkout_preview(
    payload: CustomerCheckoutPreviewIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerCheckoutPreviewOut:
    return await _build_checkout_preview(db=db, current_user=current_user, payload=payload)


@router.post("/orders", response_model=CustomerOrderOut)
async def create_order(
    payload: CustomerOrderCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerOrderOut:
    order = await create_customer_order(db=db, payload=payload, current_user=current_user)
    await db.commit()
    items = list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all())
    return _serialize_order(order, items, await _load_order_sku_map(db, items))


@router.get("/orders", response_model=list[CustomerOrderOut])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerOrderOut]:
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.customer_id == current_user.id, Order.status != OrderStatus.DELETED)
            .order_by(desc(Order.id))
            .limit(100)
        )
    ).all()
    result: list[CustomerOrderOut] = []
    changed = False
    for order in orders:
        changed = await cancel_order_if_expired(db, order, settings.ORDER_AUTO_CANCEL_MINUTES) or changed
        items = list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all())
        result.append(_serialize_order(order, items, await _load_order_sku_map(db, items)))
    if changed:
        await db.commit()
    return result


@router.get("/orders/{order_id}", response_model=CustomerOrderOut)
async def get_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerOrderOut:
    order = await db.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == current_user.id, Order.status != OrderStatus.DELETED)
    )
    if not order:
        raise not_found("order not found")
    if await cancel_order_if_expired(db, order, settings.ORDER_AUTO_CANCEL_MINUTES):
        await db.commit()
    items = list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all())
    return _serialize_order(order, items, await _load_order_sku_map(db, items))


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("only pending_payment order can be canceled")
    order = await cancel_customer_order(db=db, order=order, operator=current_user, note="customer canceled order")
    await db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "status": order.status.value}


@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.customer_id == current_user.id,
            Order.status.in_([OrderStatus.COMPLETED, OrderStatus.CANCELED]),
        )
    )
    if not order:
        raise bad_request("only completed or canceled orders can be deleted")
    order = await delete_customer_order(db=db, order=order, operator=current_user, note="customer deleted order")
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "deleted_at": order.deleted_at.isoformat() if order.deleted_at else None,
    }


@router.post("/orders/{order_id}/confirm-receipt", response_model=CustomerOrderOut)
async def confirm_receipt(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerOrderOut:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.SHIPPED:
        raise bad_request("only shipped order can be confirmed")
    order = await complete_customer_order(db=db, order=order, operator=current_user, source="customer")
    await db.commit()
    items = list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all())
    return _serialize_order(order, items, await _load_order_sku_map(db, items))


@router.post("/orders/{order_id}/wechat-pay", response_model=WechatPayCreateOut)
async def create_wechat_payment(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WechatPayCreateOut:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    if await cancel_order_if_expired(db, order, settings.ORDER_AUTO_CANCEL_MINUTES):
        await db.commit()
        raise bad_request("订单支付已超时，已自动取消")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order status is not pending_payment")
    if order.payment_method != PaymentMethod.WECHAT_PAY:
        raise bad_request("order is not using wechat_pay")
    if current_user.role == UserRole.WHOLESALE and current_user.profile and not current_user.profile.is_verified_wholesale:
        raise bad_request("wholesale qualification not verified")

    existing = await db.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.order_id == order.id,
            PaymentRecord.channel == "wechat_jsapi",
            PaymentRecord.status == PaymentStatus.PENDING,
        )
        .order_by(PaymentRecord.id.desc())
    )
    if existing and existing.prepay_id:
        jsapi_params = None if settings.WECHAT_PAY_MOCK else build_jsapi_pay_params(existing.prepay_id)
        return WechatPayCreateOut(
            payment_no=existing.payment_no,
            order_no=order.order_no,
            status=existing.status.value,
            amount=f"{Decimal(existing.amount):.2f}",
            prepay_id=existing.prepay_id,
            jsapi_params=jsapi_params,
            message="reuse existing prepay",
        )

    openid = current_user.profile.wechat_openid if current_user.profile else None
    if not openid and not settings.WECHAT_PAY_MOCK:
        raise bad_request("wechat openid is required")
    openid = openid or f"mock_openid_{current_user.id}"

    payment = PaymentRecord(
        payment_no=f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
        order_id=order.id,
        channel="wechat_jsapi",
        status=PaymentStatus.PENDING,
        amount=Decimal(order.payable_amount),
        openid=openid,
        provider_payload={"mode": "mock_jsapi" if settings.WECHAT_PAY_MOCK else "wechat_v3_jsapi"},
    )
    if settings.WECHAT_PAY_MOCK:
        payment.prepay_id = f"mock_prepay_{order.order_no}"
        jsapi_params = None
    else:
        rsp = await create_jsapi_transaction(
            order_no=order.order_no,
            amount=Decimal(order.payable_amount),
            openid=openid,
            description=f"Order {order.order_no}",
        )
        if not rsp.prepay_id:
            raise bad_request("wechat jsapi create failed")
        payment.prepay_id = rsp.prepay_id
        payment.provider_payload = rsp.raw or {}
        jsapi_params = build_jsapi_pay_params(payment.prepay_id)

    db.add(payment)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="payment",
        entity_id=payment.id,
        entity_no=payment.payment_no,
        action_code="payment.created",
        action_label="发起微信支付",
        source="customer",
        actor=current_user,
        after_data={
            "status": payment.status.value,
            "channel": payment.channel,
            "amount": f"{payment.amount:.2f}",
            "prepay_id": payment.prepay_id,
        },
    )
    await db.commit()
    return WechatPayCreateOut(
        payment_no=payment.payment_no,
        order_no=order.order_no,
        status=payment.status.value,
        amount=f"{Decimal(payment.amount):.2f}",
        prepay_id=payment.prepay_id,
        jsapi_params=jsapi_params,
        message="mock jsapi created" if settings.WECHAT_PAY_MOCK else "wechat jsapi created",
    )


@router.post("/wholesale-applications")
async def create_wholesale_application(
    payload: WholesaleApplicationCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if current_user.role == UserRole.WHOLESALE:
        raise bad_request("user is already wholesale")
    active = await db.scalar(
        select(WholesaleApplication.id).where(
            WholesaleApplication.user_id == current_user.id,
            WholesaleApplication.status == WholesaleApplicationStatus.PENDING,
        )
    )
    if active:
        raise bad_request("pending wholesale application already exists")
    row = WholesaleApplication(
        user_id=current_user.id,
        company_name=payload.company_name,
        store_name=payload.store_name,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        business_license_url=payload.business_license_url,
        remark=payload.remark,
    )
    db.add(row)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="wholesale_application",
        entity_id=row.id,
        entity_no=str(row.id),
        action_code="wholesale_application.created",
        action_label="提交批发申请",
        source="customer",
        actor=current_user,
        after_data={
            "status": row.status.value,
            "company_name": row.company_name,
            "store_name": row.store_name,
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
        },
        evidence={"business_license_url": row.business_license_url} if row.business_license_url else {},
        note=row.remark,
    )
    await create_customer_notification(
        db,
        user_id=current_user.id,
        title="批发申请已提交",
        summary=f"批发申请 #{row.id} 已提交，等待审核。",
        kind="wholesale",
        route="/pages/wholesale/apply",
    )
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "status": row.status.value}


@router.get("/wholesale-applications", response_model=list[WholesaleApplicationOut])
async def list_my_wholesale_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[WholesaleApplicationOut]:
    user = await db.scalar(select(User).where(User.id == current_user.id))
    if not user:
        raise not_found("user not found")
    rows = (
        await db.scalars(
            select(WholesaleApplication)
            .where(WholesaleApplication.user_id == current_user.id)
            .order_by(desc(WholesaleApplication.id))
            .limit(20)
        )
    ).all()
    return [
        WholesaleApplicationOut(
            id=row.id,
            status=row.status.value,
            effective_status=_resolve_application_effective_status(user, row),
            company_name=row.company_name,
            store_name=row.store_name,
            contact_name=row.contact_name,
            contact_phone=row.contact_phone,
            business_license_url=row.business_license_url,
            remark=row.remark,
            review_note=row.review_note,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/aftersales", response_model=CustomerAfterSaleOut)
async def create_aftersale(
    payload: CustomerAfterSaleCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAfterSaleOut:
    order = await db.scalar(select(Order).where(Order.id == payload.order_id, Order.customer_id == current_user.id))
    if not order:
        raise not_found("order not found")
    first_item = await db.scalar(
        select(OrderItem)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.id)
    )
    row = AfterSaleRequest(
        order_id=order.id,
        customer_id=current_user.id,
        reason=payload.reason,
        custom_reason_text=payload.custom_reason_text,
        refund_amount=payload.requested_amount,
        chat_proof_url=payload.chat_proof_url,
        note=payload.note,
        customer_note=payload.note,
        status=AfterSaleStatus.PENDING,
    )
    db.add(row)
    await db.flush()
    await write_business_event(
        db=db,
        entity_type="aftersale",
        entity_id=row.id,
        entity_no=f"AS{row.id}",
        action_code="aftersale.created",
        action_label="提交售后",
        source="customer",
        actor=current_user,
        after_data={
            "status": row.status.value,
            "reason": row.reason.value,
            "custom_reason_text": row.custom_reason_text,
            "requested_amount": f"{payload.requested_amount:.2f}" if payload.requested_amount is not None else None,
        },
        evidence={"chat_proof_url": row.chat_proof_url} if row.chat_proof_url else {},
        note=row.note,
    )
    await create_customer_notification(
        db,
        user_id=current_user.id,
        title="售后服务进度通知",
        summary=f"售后单 AS{row.id} 已提交，店里会尽快处理。",
        kind="aftersale",
        route="/pages/aftersale/list",
        push_event_key="aftersale_created",
        push_payload={
            "order_no": order.order_no,
            "product_name": first_item.product_name_snapshot if first_item else "订单商品",
            "aftersale_type": payload.reason.value,
            "status": "待处理",
            "amount": f"{payload.requested_amount:.2f}" if payload.requested_amount is not None else "0.00",
            "note": row.note or "店里会尽快处理。",
            "time": row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
        },
    )
    await db.commit()
    await db.refresh(row)
    return CustomerAfterSaleOut(
        id=row.id,
        order_id=row.order_id,
        order_no=order.order_no,
        reason=row.reason.value,
        custom_reason_text=row.custom_reason_text,
        process_type=row.process_type.value if row.process_type else None,
        refund_amount=Decimal(row.refund_amount) if row.refund_amount is not None else None,
        chat_proof_url=row.chat_proof_url,
        status=row.status.value,
        note=row.note,
        created_at=row.created_at.isoformat(),
    )


@router.get("/aftersales", response_model=list[CustomerAfterSaleOut])
async def list_aftersales(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerAfterSaleOut]:
    rows = (
        await db.execute(
            select(AfterSaleRequest, Order.order_no)
            .join(Order, Order.id == AfterSaleRequest.order_id)
            .where(AfterSaleRequest.customer_id == current_user.id, AfterSaleRequest.deleted_at.is_(None))
            .order_by(desc(AfterSaleRequest.id))
            .limit(100)
        )
    ).all()
    return [
        CustomerAfterSaleOut(
            id=row.id,
            order_id=row.order_id,
            order_no=order_no,
            reason=row.reason.value,
            custom_reason_text=row.custom_reason_text,
            process_type=row.process_type.value if row.process_type else None,
            refund_amount=Decimal(row.refund_amount) if row.refund_amount is not None else None,
            chat_proof_url=row.chat_proof_url,
            status=row.status.value,
            note=row.customer_note or row.note,
            created_at=row.created_at.isoformat(),
        )
        for row, order_no in rows
    ]


@router.get("/cart", response_model=list[CustomerCartItemOut])
async def list_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerCartItemOut]:
    return await _load_customer_cart_items(db, current_user)


@router.put("/cart/items/{sku_id}", response_model=CustomerCartItemOut)
async def upsert_cart_item(
    sku_id: int,
    payload: CustomerCartUpsertIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerCartItemOut:
    sku = await db.scalar(select(ProductSKU).options(selectinload(ProductSKU.product)).where(ProductSKU.id == sku_id))
    if not sku or not sku.is_active:
        raise not_found("sku not found")

    row = await db.scalar(
        select(CustomerCartItem).where(
            CustomerCartItem.user_id == current_user.id,
            CustomerCartItem.sku_id == sku_id,
        )
    )
    if row:
        row.quantity = payload.quantity
        row.selected = payload.selected
    else:
        row = CustomerCartItem(
            user_id=current_user.id,
            sku_id=sku_id,
            quantity=payload.quantity,
            selected=payload.selected,
        )
        db.add(row)
    await db.commit()
    return _serialize_cart_item_with_sku(row, sku, current_user)


@router.post("/cart/batch-sync", response_model=CustomerCartBatchSyncOut)
async def batch_sync_cart(
    payload: CustomerCartBatchSyncIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerCartBatchSyncOut:
    issues: list[CustomerCartBatchSyncIssueOut] = []
    synced_count = 0
    removed_count = 0
    effective_role = UserRole.WHOLESALE if _can_use_wholesale_scope(current_user) else UserRole.RETAIL
    expected_sku_type = _resolve_expected_sku_type(effective_role)

    existing_rows = (
        await db.scalars(select(CustomerCartItem).where(CustomerCartItem.user_id == current_user.id))
    ).all()
    existing_map = {row.sku_id: row for row in existing_rows}

    requested_ids = [item.sku_id for item in payload.items]
    sku_rows = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id.in_(requested_ids))
        )
    ).all() if requested_ids else []
    sku_map = {sku.id: sku for sku in sku_rows}

    if payload.replace_existing:
        for row in existing_rows:
            if row.sku_id not in requested_ids:
                await db.delete(row)
                removed_count += 1

    for item in payload.items:
        sku = sku_map.get(item.sku_id)
        if not sku or not sku.is_active or not sku.product or not sku.product.is_active:
            issues.append(CustomerCartBatchSyncIssueOut(sku_id=item.sku_id, reason="sku not found"))
            continue
        resolved_sku = await _resolve_role_sku(db, sku, expected_sku_type)
        sku = resolved_sku
        if effective_role == UserRole.RETAIL and not sku.product.supports_retail:
            issues.append(CustomerCartBatchSyncIssueOut(sku_id=sku.id, product_name=sku.product.name, reason="product is not available for retail"))
            continue
        if effective_role == UserRole.WHOLESALE and not sku.product.supports_wholesale:
            issues.append(CustomerCartBatchSyncIssueOut(sku_id=sku.id, product_name=sku.product.name, reason="product is not available for wholesale"))
            continue

        min_required_qty = sku.min_wholesale_qty if effective_role == UserRole.WHOLESALE else sku.min_sale_qty
        if item.quantity < min_required_qty:
            issues.append(
                CustomerCartBatchSyncIssueOut(
                    sku_id=sku.id,
                    product_name=sku.product.name,
                    reason=f"quantity must be at least {min_required_qty}",
                )
            )
            continue

        row = existing_map.get(sku.id)
        if row:
            row.quantity = item.quantity
            row.selected = item.selected
        else:
            row = CustomerCartItem(
                user_id=current_user.id,
                sku_id=sku.id,
                quantity=item.quantity,
                selected=item.selected,
            )
            db.add(row)
        synced_count += 1

    await db.commit()
    cart_items = await _load_customer_cart_items(db, current_user)
    return CustomerCartBatchSyncOut(
        synced_count=synced_count,
        removed_count=removed_count,
        cart_items=cart_items,
        issues=issues,
    )


@router.delete("/cart/items/{sku_id}")
async def remove_cart_item(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerCartItem).where(
            CustomerCartItem.user_id == current_user.id,
            CustomerCartItem.sku_id == sku_id,
        )
    )
    if not row:
        return {"removed": 0}
    await db.delete(row)
    await db.commit()
    return {"removed": 1}


@router.delete("/cart/clear")
async def clear_cart(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(select(CustomerCartItem).where(CustomerCartItem.user_id == current_user.id))
    ).all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"cleared": len(rows)}


@router.get("/addresses", response_model=list[CustomerAddressOut])
async def list_addresses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerAddressOut]:
    rows = (
        await db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.id))
        )
    ).all()
    return [_serialize_address(row) for row in rows]


@router.post("/addresses", response_model=CustomerAddressOut)
async def create_address(
    payload: CustomerAddressIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    existing = (
        await db.scalars(select(CustomerAddress).where(CustomerAddress.user_id == current_user.id))
    ).all()
    is_default = payload.is_default or len(existing) == 0
    if is_default:
        for item in existing:
            item.is_default = False
    row = CustomerAddress(
        user_id=current_user.id,
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
        region=payload.region.strip(),
        detail=payload.detail.strip(),
        tag=payload.tag.strip() or "常用",
        is_default=is_default,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_address(row)


@router.patch("/addresses/{address_id}", response_model=CustomerAddressOut)
async def update_address(
    address_id: int,
    payload: CustomerAddressIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerAddressOut:
    row = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not row:
        raise not_found("address not found")
    if payload.is_default:
        rows = (
            await db.scalars(select(CustomerAddress).where(CustomerAddress.user_id == current_user.id))
        ).all()
        for item in rows:
            item.is_default = item.id == row.id
    row.contact_name = payload.contact_name.strip()
    row.phone = payload.phone.strip()
    row.region = payload.region.strip()
    row.detail = payload.detail.strip()
    row.tag = payload.tag.strip() or "常用"
    row.is_default = payload.is_default
    await db.commit()
    await db.refresh(row)
    return _serialize_address(row)


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.user_id == current_user.id)
    )
    if not row:
        return {"removed": 0}
    removed_default = row.is_default
    await db.delete(row)
    await db.commit()

    if removed_default:
        first = await db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(desc(CustomerAddress.id))
        )
        if first:
            first.is_default = True
            await db.commit()
    return {"removed": 1}


@router.get("/search-histories", response_model=list[CustomerSearchHistoryOut])
async def list_search_histories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerSearchHistoryOut]:
    rows = (
        await db.scalars(
            select(CustomerSearchHistory)
            .where(CustomerSearchHistory.user_id == current_user.id)
            .order_by(desc(CustomerSearchHistory.id))
            .limit(20)
        )
    ).all()
    return [
        CustomerSearchHistoryOut(id=row.id, keyword=row.keyword, created_at=row.created_at.isoformat())
        for row in rows
    ]


@router.post("/search-histories", response_model=CustomerSearchHistoryOut)
async def add_search_history(
    payload: CustomerSearchHistoryIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerSearchHistoryOut:
    keyword = payload.keyword.strip()
    existing = (
        await db.scalars(
            select(CustomerSearchHistory).where(
                CustomerSearchHistory.user_id == current_user.id,
                CustomerSearchHistory.keyword == keyword,
            )
        )
    ).all()
    for row in existing:
        await db.delete(row)

    row = CustomerSearchHistory(user_id=current_user.id, keyword=keyword)
    db.add(row)
    await db.commit()
    await db.refresh(row)

    rows = (
        await db.scalars(
            select(CustomerSearchHistory)
            .where(CustomerSearchHistory.user_id == current_user.id)
            .order_by(desc(CustomerSearchHistory.id))
        )
    ).all()
    for stale in rows[20:]:
        await db.delete(stale)
    await db.commit()

    return CustomerSearchHistoryOut(id=row.id, keyword=row.keyword, created_at=row.created_at.isoformat())


@router.delete("/search-histories")
async def clear_search_histories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(
            select(CustomerSearchHistory).where(CustomerSearchHistory.user_id == current_user.id)
        )
    ).all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"cleared": len(rows)}


@router.get("/notifications", response_model=list[CustomerNotificationOut])
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CustomerNotificationOut]:
    legacy_system_summary = "消息中心已启用，订单、售后和批发审核结果会在这里汇总。"
    replacement_system_summary = "请先开启消息提醒授权，之后订单、售后和批发审核结果会在这里汇总。"
    rows = (
        await db.scalars(
            select(CustomerNotification)
            .where(CustomerNotification.user_id == current_user.id)
            .order_by(desc(CustomerNotification.id))
            .limit(50)
        )
    ).all()

    updated = False
    for row in rows:
        if row.title == "系统提示" and row.summary == legacy_system_summary:
            row.summary = replacement_system_summary
            updated = True
    if updated:
        await db.commit()

    if not rows:
        seed_rows = [
            CustomerNotification(
                user_id=current_user.id,
                title="系统提示",
                summary=replacement_system_summary,
                kind="system",
                route="/pages/order/list",
                unread=True,
            ),
        ]
        for item in seed_rows:
            db.add(item)
        await db.commit()
        rows = (
            await db.scalars(
                select(CustomerNotification)
                .where(CustomerNotification.user_id == current_user.id)
                .order_by(desc(CustomerNotification.id))
                .limit(50)
            )
        ).all()

    return [
        CustomerNotificationOut(
            id=row.id,
            title=row.title,
            summary=row.summary,
            kind=row.kind,
            route=row.route,
            unread=row.unread,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(
        select(CustomerNotification).where(
            CustomerNotification.id == notification_id,
            CustomerNotification.user_id == current_user.id,
        )
    )
    if not row:
        return {"updated": 0}
    row.unread = False
    await db.commit()
    return {"updated": 1}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    rows = (
        await db.scalars(
            select(CustomerNotification).where(CustomerNotification.user_id == current_user.id)
        )
    ).all()
    updated = 0
    for row in rows:
        if row.unread:
            row.unread = False
            updated += 1
    await db.commit()
    return {"updated": updated}
