import asyncio
import json
from pathlib import Path
from uuid import uuid4
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.db.session import SessionLocal, get_db
from app.models.aftersale import AfterSaleRequest
from app.models.customer_runtime import CustomerAddress, CustomerCartItem, CustomerNotification, CustomerProductFavorite
from app.models.enums import AfterSaleProcessType, AfterSaleStatus, OrderStatus, PaymentMethod, PaymentStatus, SKUType, UserRole
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.image_generation import ImageGenerationHistory
from app.models.image_prompt_template import ImagePromptTemplate
from app.models.print_job import PrintJob
from app.models.product import Product, ProductSKU
from app.models.user import CustomerProfile, User
from app.schemas.employee import (
    EmployeeCancelOrderIn,
    EmployeeConfirmOfflinePaymentIn,
    EmployeeOrderNoteIn,
    EmployeeResolveAfterSaleIn,
    EmployeeSetDeliverySignedIn,
    EmployeeShipOrderIn,
    EmployeeImageGenerateIn,
    EmployeeImagePromptTemplateIn,
    EmployeeQuickProductIn,
    EmployeeWorkbenchSummaryOut,
)
from app.services.events import write_business_event
from app.services.notifications import create_customer_notification
from app.services.orders import cancel_order, complete_order, mark_order_paid, ship_order, sync_wechat_shipping_upload
from app.services.image_ai import IMAGE_CONTENT_TYPES, detect_image_content_type, generate_store_image
from app.services.storefront_config import load_storefront_config

EVIDENCE_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "employee-evidence"
IMAGE_OUTPUT_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "employee-images"
EVIDENCE_IMAGE_EXTENSIONS = set(IMAGE_CONTENT_TYPES)
EVIDENCE_MAX_IMAGE_SIZE = 10 * 1024 * 1024

router = APIRouter(prefix="/employee", tags=["employee"])


def _image_urls(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _print_customer_identity(order: Order, customer: User | None) -> tuple[str, str]:
    profile = customer.profile if customer else None
    recipient = order.shipping_recipient or (profile.contact_name if profile else None) or (profile.display_name if profile else None) or (customer.username if customer else "")
    phone = order.shipping_phone or (profile.phone if profile else "")
    return recipient, phone


@router.get("/customers", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_employee_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[dict]:
    stmt = (
        select(User)
        .options(selectinload(User.profile))
        .where(User.role.in_({UserRole.RETAIL, UserRole.WHOLESALE}), User.deleted_at.is_(None))
        .order_by(desc(User.id))
        .limit(300)
    )
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.profile.has(CustomerProfile.display_name.ilike(like)), User.profile.has(CustomerProfile.phone.ilike(like))))
    rows = (await db.scalars(stmt)).all()
    customer_ids = [row.id for row in rows]
    order_stats = (
        await db.execute(
            select(Order.customer_id, func.count(Order.id), func.coalesce(func.sum(Order.payable_amount), 0))
            .where(Order.customer_id.in_(customer_ids), Order.deleted_at.is_(None))
            .group_by(Order.customer_id)
        )
    ).all() if customer_ids else []
    stats_map = {customer_id: (count, amount) for customer_id, count, amount in order_stats}
    return [
        {
            "id": row.id,
            "username": row.username,
            "role": row.role.value,
            "is_active": row.is_active,
            "is_blacklisted": row.is_blacklisted,
            "is_flagged": row.is_flagged,
            "display_name": row.profile.display_name if row.profile else None,
            "phone": row.profile.phone if row.profile else None,
            "avatar_url": row.profile.avatar_url if row.profile else None,
            "company_name": row.profile.company_name if row.profile else None,
            "store_name": row.profile.store_name if row.profile else None,
            "contact_name": row.profile.contact_name if row.profile else None,
            "address": row.profile.address if row.profile else None,
            "note": row.profile.note if row.profile else None,
            "business_license_url": row.profile.business_license_url if row.profile else None,
            "is_verified_wholesale": row.profile.is_verified_wholesale if row.profile else False,
            "order_count": int(stats_map.get(row.id, (0, 0))[0]),
            "order_amount": f"{Decimal(stats_map.get(row.id, (0, 0))[1]):.2f}",
        }
        for row in rows
    ]


@router.get("/customers/{customer_id}", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def get_employee_customer_detail(
    customer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == customer_id, User.role.in_({UserRole.RETAIL, UserRole.WHOLESALE}), User.deleted_at.is_(None))
    )
    if not user:
        raise not_found("customer not found")
    orders = (await db.scalars(select(Order).where(Order.customer_id == user.id, Order.deleted_at.is_(None)).order_by(desc(Order.id)).limit(50))).all()
    aftersales = (await db.scalars(select(AfterSaleRequest).where(AfterSaleRequest.customer_id == user.id, AfterSaleRequest.deleted_at.is_(None)).order_by(desc(AfterSaleRequest.id)).limit(50))).all()
    addresses = (await db.scalars(select(CustomerAddress).where(CustomerAddress.user_id == user.id).order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.id)))).all()
    order_no_by_id = {order.id: order.order_no for order in orders}
    favorite_count = await db.scalar(select(func.count(CustomerProductFavorite.id)).where(CustomerProductFavorite.user_id == user.id)) or 0
    cart_count = await db.scalar(select(func.count(CustomerCartItem.id)).where(CustomerCartItem.user_id == user.id)) or 0
    unread_notification_count = await db.scalar(select(func.count(CustomerNotification.id)).where(CustomerNotification.user_id == user.id, CustomerNotification.unread.is_(True))) or 0
    profile = user.profile
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_blacklisted": user.is_blacklisted,
        "is_flagged": user.is_flagged,
        "display_name": profile.display_name if profile else None,
        "phone": profile.phone if profile else None,
        "avatar_url": profile.avatar_url if profile else None,
        "company_name": profile.company_name if profile else None,
        "store_name": profile.store_name if profile else None,
        "contact_name": profile.contact_name if profile else None,
        "address": profile.address if profile else None,
        "note": profile.note if profile else None,
        "business_license_url": profile.business_license_url if profile else None,
        "is_verified_wholesale": profile.is_verified_wholesale if profile else False,
        "favorite_count": int(favorite_count),
        "cart_count": int(cart_count),
        "unread_notification_count": int(unread_notification_count),
        "addresses": [{"id": row.id, "contact_name": row.contact_name, "phone": row.phone, "region": row.region, "detail": row.detail, "tag": row.tag, "is_default": row.is_default} for row in addresses],
        "orders": [{"id": row.id, "order_no": row.order_no, "status": row.status.value, "amount": _amount_to_str(row.payable_amount), "created_at": row.created_at.isoformat()} for row in orders],
        "aftersales": [{"id": row.id, "order_no": order_no_by_id.get(row.order_id), "status": row.status.value, "reason": row.reason.value, "created_at": row.created_at.isoformat()} for row in aftersales],
    }


@router.get("/products", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_employee_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[dict]:
    stmt = select(Product).options(selectinload(Product.skus)).order_by(desc(Product.id)).limit(300)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.model_name.ilike(like), Product.product_code.ilike(like)))
    rows = (await db.scalars(stmt)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "model_name": row.model_name,
            "product_code": row.product_code,
            "brand": row.brand,
            "category": row.category,
            "description": row.description,
            "image_urls": _image_urls(row.image_urls),
            "supports_retail": row.supports_retail,
            "supports_wholesale": row.supports_wholesale,
            "has_dual_price": row.has_dual_price,
            "is_active": row.is_active,
            "skus": [
                {
                    "id": sku.id,
                    "sku_code": sku.sku_code,
                    "sku_type": sku.sku_type.value,
                    "spec_value_1": sku.spec_value_1,
                    "spec_value_2": sku.spec_value_2,
                    "sku_label": sku.sku_label,
                    "online_stock": sku.online_stock,
                    "retail_price": f"{Decimal(sku.retail_price):.2f}",
                    "wholesale_price": f"{Decimal(sku.wholesale_price):.2f}",
                    "min_sale_qty": sku.min_sale_qty,
                    "min_wholesale_qty": sku.min_wholesale_qty,
                    "is_active": sku.is_active,
                }
                for sku in sorted(row.skus, key=lambda item: (item.sku_type.value, item.spec_value_1 or "", item.spec_value_2 or "", item.id))
            ],
        }
        for row in rows
    ]


def _quick_product_payload(row: Product) -> dict:
    retail = next((sku for sku in row.skus if sku.sku_type.value == "retail"), None)
    wholesale = next((sku for sku in row.skus if sku.sku_type.value == "wholesale"), None)
    return {
        "name": row.name,
        "product_code": row.product_code,
        "category": row.category,
        "description": row.description,
        "image_urls": _image_urls(row.image_urls),
        "retail_price": f"{Decimal(retail.retail_price):.2f}" if retail else None,
        "wholesale_price": f"{Decimal(wholesale.wholesale_price):.2f}" if wholesale else None,
        "min_wholesale_qty": wholesale.min_wholesale_qty if wholesale else 1,
        "is_active": row.is_active,
    }


@router.post("/products", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def create_employee_quick_product(
    payload: EmployeeQuickProductIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    code = payload.product_code.strip().upper()
    if await db.scalar(select(Product.id).where(Product.product_code == code)):
        raise bad_request("product_code already exists")
    row = Product(
        name=payload.name.strip(), product_code=code, category=(payload.category or "").strip() or None,
        description=(payload.description or "").strip() or None, image_urls=json.dumps(payload.image_urls),
        supports_retail=payload.retail_price is not None, supports_wholesale=payload.wholesale_price is not None,
        has_dual_price=payload.retail_price is not None and payload.wholesale_price is not None, is_active=payload.is_active,
    )
    db.add(row)
    await db.flush()
    # ponytail: catalog does not track physical stock; a high internal availability keeps checkout usable.
    if payload.retail_price is not None:
        db.add(ProductSKU(product_id=row.id, sku_code=f"{code}-R", sku_type=SKUType.RETAIL, sku_label="默认规格", online_stock=999, retail_price=payload.retail_price, wholesale_price=payload.wholesale_price or 0, min_sale_qty=1, min_wholesale_qty=payload.min_wholesale_qty, is_active=payload.is_active))
    if payload.wholesale_price is not None:
        db.add(ProductSKU(product_id=row.id, sku_code=f"{code}-W", sku_type=SKUType.WHOLESALE, sku_label="默认规格", online_stock=999, retail_price=payload.retail_price, wholesale_price=payload.wholesale_price, min_sale_qty=1, min_wholesale_qty=payload.min_wholesale_qty, is_active=payload.is_active))
    await write_business_event(db=db, entity_type="product", entity_id=row.id, entity_no=code, action_code="product.quick_created", action_label="快速上架商品", source="employee", actor=current_user, after_data={"name": row.name, "category": row.category})
    await db.commit()
    return {"id": row.id, "product_code": code}


@router.patch("/products/{product_id}", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def update_employee_quick_product(
    product_id: int,
    payload: EmployeeQuickProductIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(select(Product).options(selectinload(Product.skus)).where(Product.id == product_id))
    if not row:
        raise not_found("product not found")
    if len(row.skus) > 2:
        raise bad_request("multi-SKU products must be maintained in admin")
    before = _quick_product_payload(row)
    code = payload.product_code.strip().upper()
    if code != row.product_code and await db.scalar(select(Product.id).where(Product.product_code == code, Product.id != row.id)):
        raise bad_request("product_code already exists")
    row.name, row.product_code, row.category, row.description, row.image_urls, row.is_active = payload.name.strip(), code, (payload.category or "").strip() or None, (payload.description or "").strip() or None, json.dumps(payload.image_urls), payload.is_active
    row.supports_retail = payload.retail_price is not None
    row.supports_wholesale = payload.wholesale_price is not None
    row.has_dual_price = payload.retail_price is not None and payload.wholesale_price is not None
    retail = next((sku for sku in row.skus if sku.sku_type.value == "retail"), None)
    wholesale = next((sku for sku in row.skus if sku.sku_type.value == "wholesale"), None)
    if payload.retail_price is None and retail:
        await db.delete(retail)
    elif payload.retail_price is not None and retail:
        retail.sku_code, retail.retail_price, retail.wholesale_price, retail.is_active = f"{code}-R", payload.retail_price, payload.wholesale_price or 0, payload.is_active
    elif payload.retail_price is not None:
        db.add(ProductSKU(product_id=row.id, sku_code=f"{code}-R", sku_type=SKUType.RETAIL, sku_label="默认规格", online_stock=999, retail_price=payload.retail_price, wholesale_price=payload.wholesale_price or 0, min_sale_qty=1, min_wholesale_qty=payload.min_wholesale_qty, is_active=payload.is_active))
    if payload.wholesale_price is None and wholesale:
        await db.delete(wholesale)
    elif payload.wholesale_price is not None and wholesale:
        wholesale.sku_code, wholesale.retail_price, wholesale.wholesale_price, wholesale.min_wholesale_qty, wholesale.is_active = f"{code}-W", payload.retail_price or 0, payload.wholesale_price, payload.min_wholesale_qty, payload.is_active
    elif payload.wholesale_price is not None:
        db.add(ProductSKU(product_id=row.id, sku_code=f"{code}-W", sku_type=SKUType.WHOLESALE, sku_label="默认规格", online_stock=999, retail_price=payload.retail_price or 0, wholesale_price=payload.wholesale_price, min_sale_qty=1, min_wholesale_qty=payload.min_wholesale_qty, is_active=payload.is_active))
    await write_business_event(db=db, entity_type="product", entity_id=row.id, entity_no=row.product_code, action_code="product.quick_updated", action_label="快速编辑商品", source="employee", actor=current_user, before_data=before, after_data={"name": row.name, "category": row.category, "is_active": row.is_active})
    await db.commit()
    return {"id": row.id, "product_code": row.product_code}


@router.post("/upload-evidence", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def upload_employee_evidence(file: UploadFile = File(...)) -> dict:
    """Store an internal handoff or aftersales photo without granting product admin access."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in EVIDENCE_IMAGE_EXTENSIONS:
        raise bad_request("unsupported image type")
    content = await file.read()
    if not content:
        raise bad_request("empty file")
    if len(content) > EVIDENCE_MAX_IMAGE_SIZE:
        raise bad_request("image size exceeds 10MB")
    if detect_image_content_type(content) != IMAGE_CONTENT_TYPES[ext]:
        raise bad_request("image content does not match its file type")
    EVIDENCE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex}{ext}"
    (EVIDENCE_UPLOAD_ROOT / name).write_bytes(content)
    return {"url": f"/api/v1/employee/evidence/{name}"}


@router.get("/evidence/{file_name}")
async def get_employee_evidence(file_name: str) -> FileResponse:
    path = EVIDENCE_UPLOAD_ROOT / Path(file_name).name
    if not path.is_file():
        raise not_found("evidence not found")
    return FileResponse(path)


@router.get("/image-ai/status", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def get_image_ai_status() -> dict:
    settings = load_storefront_config(include_secrets=False).get("image_ai_settings") or {}
    return {
        "enabled": bool(settings.get("enabled")),
        "configured": bool(settings.get("api_key_set") and settings.get("base_url") and settings.get("model")),
        "max_input_images": int(settings.get("max_input_images") or 1),
    }


async def _run_image_generation(*, history_id: int, settings: dict, reference_paths: list[Path]) -> None:
    async with SessionLocal() as db:
        history = await db.get(ImageGenerationHistory, history_id)
        if not history:
            return
        try:
            image = await generate_store_image(settings=settings, prompt=history.prompt, reference_paths=reference_paths)
            if not image or len(image) > 20 * 1024 * 1024:
                raise ValueError("generated image is invalid")
            IMAGE_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            name = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex}.png"
            (IMAGE_OUTPUT_ROOT / name).write_bytes(image)
            history.status = "succeeded"
            history.result_url = f"/api/v1/employee/images/{name}"
        except HTTPException as error:
            history.status = "failed"
            history.error_message = str(error.detail)[:500]
        except Exception as error:
            history.status = "failed"
            history.error_message = str(error)[:500]
        await db.commit()


@router.post("/image-ai/generate", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def generate_employee_image(
    payload: EmployeeImageGenerateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = load_storefront_config(include_secrets=True).get("image_ai_settings") or {}
    max_images = max(1, min(int(settings.get("max_input_images") or 1), 5))
    if len(payload.reference_urls) > max_images:
        raise bad_request(f"at most {max_images} reference images are allowed")
    reference_paths: list[Path] = []
    for url in payload.reference_urls:
        name = Path(url.split("?", 1)[0]).name
        if not name or not url.startswith("/api/v1/employee/evidence/"):
            raise bad_request("invalid reference image")
        path = EVIDENCE_UPLOAD_ROOT / name
        if not path.is_file():
            raise bad_request("reference image not found")
        reference_paths.append(path)
    history = ImageGenerationHistory(
        user_id=current_user.id,
        model_name=str(settings.get("model") or ""),
        prompt=payload.prompt.strip(),
        reference_urls=payload.reference_urls,
        status="processing",
    )
    db.add(history)
    await db.commit()
    # ponytail: a single in-process task survives client navigation; use a queue if generation volume exceeds one server.
    asyncio.create_task(_run_image_generation(history_id=history.id, settings=settings, reference_paths=reference_paths))
    return {"id": history.id, "status": history.status}


def _serialize_image_history(row: ImageGenerationHistory, *, username: str | None = None) -> dict:
    return {
        "id": row.id,
        "username": username,
        "model_name": row.model_name,
        "prompt": row.prompt,
        "reference_urls": row.reference_urls or [],
        "result_url": row.result_url,
        "status": row.status,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_image_prompt_template(row: ImagePromptTemplate, *, username: str | None = None) -> dict:
    return {"id": row.id, "name": row.name, "prompt": row.prompt, "is_shared": row.is_shared, "username": username}


@router.get("/image-ai/templates", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def get_employee_image_prompt_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    rows = (await db.scalars(
        select(ImagePromptTemplate)
        .where(or_(ImagePromptTemplate.is_shared.is_(True), ImagePromptTemplate.owner_user_id == current_user.id))
        .order_by(desc(ImagePromptTemplate.is_shared), desc(ImagePromptTemplate.id))
    )).all()
    return [_serialize_image_prompt_template(row, username=None if row.is_shared else current_user.username) for row in rows]


@router.post("/image-ai/templates", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def create_employee_image_prompt_template(
    payload: EmployeeImagePromptTemplateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = ImagePromptTemplate(owner_user_id=current_user.id, name=payload.name.strip(), prompt=payload.prompt.strip(), is_shared=False)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_image_prompt_template(row, username=current_user.username)


@router.delete("/image-ai/templates/{template_id}", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def delete_employee_image_prompt_template(
    template_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.scalar(select(ImagePromptTemplate).where(ImagePromptTemplate.id == template_id, ImagePromptTemplate.owner_user_id == current_user.id))
    if not row:
        raise not_found("prompt template not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.get("/image-ai/history", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def get_employee_image_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    rows = (await db.scalars(
        select(ImageGenerationHistory)
        .where(ImageGenerationHistory.user_id == current_user.id)
        .order_by(desc(ImageGenerationHistory.id))
        .limit(50)
    )).all()
    return [_serialize_image_history(row, username=current_user.username) for row in rows]


@router.get("/images/{file_name}")
async def get_employee_generated_image(file_name: str) -> FileResponse:
    path = IMAGE_OUTPUT_ROOT / Path(file_name).name
    if not path.is_file():
        raise not_found("image not found")
    return FileResponse(path)


def _amount_to_str(value: Decimal | int | float | None) -> str:
    return f"{Decimal(value or 0):.2f}"


def _first_image_url(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


@router.get(
    "/workbench-summary",
    response_model=EmployeeWorkbenchSummaryOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def get_workbench_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeWorkbenchSummaryOut:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    pending_payment_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING_PAYMENT)
    ) or 0
    awaiting_shipment_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.AWAITING_SHIPMENT)
    ) or 0
    shipped_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.SHIPPED)
    ) or 0
    pending_aftersales = await db.scalar(
        select(func.count(AfterSaleRequest.id)).where(AfterSaleRequest.status == AfterSaleStatus.PENDING, AfterSaleRequest.deleted_at.is_(None))
    ) or 0
    today_new_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    ) or 0
    today_new_aftersales = await db.scalar(
        select(func.count(AfterSaleRequest.id)).where(AfterSaleRequest.created_at >= today_start, AfterSaleRequest.deleted_at.is_(None))
    ) or 0

    return EmployeeWorkbenchSummaryOut(
        pending_payment_orders=int(pending_payment_orders),
        awaiting_shipment_orders=int(awaiting_shipment_orders),
        shipped_orders=int(shipped_orders),
        pending_aftersales=int(pending_aftersales),
        today_new_orders=int(today_new_orders),
        today_new_aftersales=int(today_new_aftersales),
    )


@router.get("/orders", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: OrderStatus | None = Query(default=None),
) -> list[dict]:
    stmt = select(Order).where(Order.deleted_at.is_(None)).order_by(desc(Order.id)).limit(300)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    rows = (await db.scalars(stmt)).all()
    order_ids = [row.id for row in rows]
    customer_ids = [row.customer_id for row in rows if row.customer_id]
    deleted_by_ids = [row.deleted_by_user_id for row in rows if getattr(row, "deleted_by_user_id", None)]

    user_ids = list({*(customer_ids or []), *(deleted_by_ids or [])})
    users = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(user_ids))
        )
    ).all() if user_ids else []
    user_map = {user.id: user for user in users}

    items = (
        await db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id.in_(order_ids))
            .order_by(OrderItem.id.asc())
        )
    ).all() if order_ids else []
    items_by_order: dict[int, list[OrderItem]] = {}
    for item in items:
        items_by_order.setdefault(item.order_id, []).append(item)

    sku_ids = list({item.sku_id for item in items if item.sku_id})
    skus = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.id.in_(sku_ids))
        )
    ).all() if sku_ids else []
    sku_image_map = {
        sku.id: _first_image_url(sku.product.image_urls if sku.product else None)
        for sku in skus
    }

    result: list[dict] = []
    for row in rows:
        user = user_map.get(row.customer_id)
        order_items = items_by_order.get(row.id, [])
        result.append(
            {
                "id": row.id,
                "order_no": row.order_no,
                "status": row.status.value,
                "buyer_role": row.buyer_role.value,
                "payment_method": row.payment_method.value,
                "shipping_mode": row.shipping_mode.value if row.shipping_mode else None,
                "shipping_recipient": row.shipping_recipient,
                "shipping_phone": row.shipping_phone,
                "shipping_address": row.shipping_address,
                "shipping_proof_url": row.shipping_proof_url,
                "shipping_evidence": row.shipping_evidence or {},
                "logistics_company": row.logistics_company,
                "fulfillment_channel": row.fulfillment_channel,
                "carrier_contact": row.carrier_contact,
                "tracking_no": row.tracking_no,
                "wechat_shipping_status": row.wechat_shipping_status,
                "wechat_shipping_error": row.wechat_shipping_error,
                "wechat_shipping_attempts": row.wechat_shipping_attempts,
                "wechat_shipping_attempted_at": row.wechat_shipping_attempted_at.isoformat() if row.wechat_shipping_attempted_at else None,
                "wechat_shipping_uploaded_at": row.wechat_shipping_uploaded_at.isoformat() if row.wechat_shipping_uploaded_at else None,
                "note": row.note,
                "customer_note": row.customer_note or row.note,
                "internal_note": row.internal_note,
                "cancellation_reason": row.cancellation_reason,
                "cancellation_source": row.cancellation_source,
                "termination_reason": row.termination_reason,
                "termination_disposition": row.termination_disposition,
                "created_at": row.created_at.isoformat(),
                "paid_at": row.paid_at.isoformat() if row.paid_at else None,
                "shipped_at": row.shipped_at.isoformat() if row.shipped_at else None,
                "delivery_signed_at": row.delivery_signed_at.isoformat() if row.delivery_signed_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "canceled_at": row.canceled_at.isoformat() if row.canceled_at else None,
                "terminated_at": row.terminated_at.isoformat() if row.terminated_at else None,
                "deleted_at": row.deleted_at.isoformat() if getattr(row, "deleted_at", None) else None,
                "deleted_by_user_id": row.deleted_by_user_id,
                "deleted_by_name": (
                    user_map[row.deleted_by_user_id].profile.display_name
                    if row.deleted_by_user_id
                    and user_map.get(row.deleted_by_user_id)
                    and user_map[row.deleted_by_user_id].profile
                    and user_map[row.deleted_by_user_id].profile.display_name
                    else (
                        user_map[row.deleted_by_user_id].username
                        if row.deleted_by_user_id and user_map.get(row.deleted_by_user_id)
                        else None
                    )
                ),
                "original_amount": _amount_to_str(row.original_amount),
                "shipping_fee": _amount_to_str(row.shipping_fee),
                "payable_amount": _amount_to_str(row.payable_amount),
                "customer_name": (
                    user.profile.display_name
                    if user and user.profile and user.profile.display_name
                    else (user.username if user else "unknown")
                ),
                "customer_phone": user.profile.phone if user and user.profile else None,
                "item_count": len(order_items),
                "item_summary": order_items[0].product_name_snapshot if order_items else None,
                "lines": [
                    {
                        "sku_id": item.sku_id,
                        "product_name": item.product_name_snapshot,
                        "sku_code": item.sku_code_snapshot,
                        "spec_value_1": item.spec_value_1_snapshot,
                        "spec_value_2": item.spec_value_2_snapshot,
                        "image_url": sku_image_map.get(item.sku_id),
                        "quantity": item.quantity,
                        "unit_price": _amount_to_str(item.unit_price),
                        "line_amount": _amount_to_str(item.line_amount),
                    }
                    for item in order_items
                ],
                # 计算字段逻辑 (店员侧)
                "can_ship": row.status == OrderStatus.AWAITING_SHIPMENT,
                "can_mark_delivered": row.status == OrderStatus.SHIPPED,
                "can_cancel": row.status == OrderStatus.PENDING_PAYMENT,
            }
        )
    return result


@router.post("/orders/{order_id}/print-pick-list", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def create_pick_list_print_job(
    order_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.deleted_at.is_(None)))
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.AWAITING_SHIPMENT:
        raise bad_request("only awaiting_shipment orders can create a pick-list print job")
    lines = (await db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id))).all()
    customer = await db.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == order.customer_id)
    ) if order.customer_id else None
    recipient, phone = _print_customer_identity(order, customer)
    storefront_config = load_storefront_config()
    store_info = storefront_config.get("store_info") or {}
    customer_service = storefront_config.get("customer_service") or {}
    shipping_channel = order.fulfillment_channel or (order.shipping_mode.value if order.shipping_mode else "")
    shipping_channel = {
        "pickup": "到店自提",
        "courier": "快递",
        "linehaul": "物流部",
        "local_delivery": "同城配送",
    }.get(shipping_channel, shipping_channel)
    job = PrintJob(
        order_id=order.id,
        requested_by_user_id=current_user.id,
        payload={
            "order_no": order.order_no,
            "recipient": recipient,
            "phone": phone,
            "address": order.shipping_address,
            "shipping_channel": shipping_channel,
            "customer_note": order.customer_note or order.note,
            "internal_note": order.internal_note,
            "total_quantity": sum(line.quantity for line in lines),
            "total_amount": str(order.payable_amount),
            "wechat_id": customer_service.get("wechat_id") or "",
            "store_phone": store_info.get("phone") or "",
            "lines": [
                {
                    "name": line.product_name_snapshot,
                    "sku_code": line.sku_code_snapshot,
                    "spec": " / ".join(item for item in [line.spec_value_1_snapshot, line.spec_value_2_snapshot] if item),
                    "quantity": line.quantity,
                    "unit_price": str(line.unit_price),
                    "line_amount": str(line.line_amount),
                }
                for line in lines
            ],
        },
    )
    db.add(job)
    await db.flush()
    await write_business_event(
        db=db, entity_type="print_job", entity_id=job.id, entity_no=order.order_no,
        action_code="print.pick_list_requested", action_label="登记配货单打印", source="employee", actor=current_user,
        after_data={"status": job.status, "document_type": job.document_type, "order_id": order.id},
    )
    await db.commit()
    return {"id": job.id, "status": job.status, "order_no": order.order_no}


@router.post(
    "/orders/{order_id}/confirm-offline-payment",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def confirm_offline_payment(
    order_id: int,
    payload: EmployeeConfirmOfflinePaymentIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.payment_method != PaymentMethod.OFFLINE_TRANSFER:
        raise bad_request("order is not offline_transfer")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise bad_request("order is not pending_payment")

    payment = PaymentRecord(
        payment_no=f"PAY{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
        order_id=order.id,
        channel="offline_transfer",
        status=PaymentStatus.PAID,
        amount=Decimal(order.payable_amount),
        note=payload.note,
        provider_payload={"confirmed_by_employee": True},
    )
    db.add(payment)
    await db.flush()
    await mark_order_paid(db=db, order=order, operator=current_user, source="employee", note=payload.note)
    await write_business_event(
        db=db,
        entity_type="payment",
        entity_id=payment.id,
        entity_no=payment.payment_no,
        action_code="payment.confirmed",
        action_label="线下收款确认",
        source="employee",
        actor=current_user,
        after_data={
            "status": payment.status.value,
            "amount": f"{payment.amount:.2f}",
            "channel": payment.channel,
            "provider_txn_no": payment.provider_txn_no,
        },
        note=payload.note,
    )
    await db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "status": order.status.value}


@router.post(
    "/orders/{order_id}/ship",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def employee_ship_order(
    order_id: int,
    payload: EmployeeShipOrderIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    order = await ship_order(
        db=db,
        order=order,
        shipping_mode=payload.shipping_mode,
        shipping_proof_url=payload.shipping_proof_url,
        shipping_evidence=payload.shipping_evidence,
        logistics_company=payload.logistics_company,
        fulfillment_channel=payload.fulfillment_channel,
        carrier_contact=payload.carrier_contact,
        tracking_no=payload.tracking_no,
        note=payload.note,
        operator=current_user,
        source="employee",
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "shipping_mode": order.shipping_mode.value if order.shipping_mode else None,
        "fulfillment_channel": order.fulfillment_channel,
        "carrier_contact": order.carrier_contact,
        "wechat_shipping_status": order.wechat_shipping_status,
        "wechat_shipping_error": order.wechat_shipping_error,
    }


@router.post(
    "/orders/{order_id}/wechat-shipping/retry",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def retry_wechat_shipping_upload(
    order_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.status not in {OrderStatus.SHIPPED, OrderStatus.COMPLETED}:
        raise bad_request("order must be handed over before retrying wechat shipping upload")
    result = await sync_wechat_shipping_upload(db=db, order=order, operator=current_user, source="employee")
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "wechat_shipping_status": order.wechat_shipping_status,
        "wechat_shipping_error": order.wechat_shipping_error,
        "wechat_shipping_attempts": order.wechat_shipping_attempts,
        "result": result,
    }


@router.post(
    "/orders/{order_id}/note",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def save_order_followup_note(
    order_id: int,
    payload: EmployeeOrderNoteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    order.internal_note = (payload.note or "").strip() or None
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.note.updated",
        action_label="订单备注更新",
        source="employee",
        actor=current_user,
        after_data={"internal_note": order.internal_note},
        note=order.internal_note,
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "note": order.internal_note,
    }


@router.post(
    "/orders/{order_id}/mark-delivered",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def mark_delivered(
    order_id: int,
    payload: EmployeeSetDeliverySignedIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    if order.status != OrderStatus.SHIPPED:
        raise bad_request("only shipped order can be marked delivered")
    order.delivery_signed_at = payload.signed_at
    await write_business_event(
        db=db,
        entity_type="order",
        entity_id=order.id,
        entity_no=order.order_no,
        action_code="order.signed",
        action_label="客户签收",
        source="employee",
        actor=current_user,
        after_data={"delivery_signed_at": order.delivery_signed_at.isoformat()},
    )
    await complete_order(db=db, order=order, operator=current_user, source="employee")
    await db.commit()
    return {
        "order_id": order.id,
        "delivery_signed_at": order.delivery_signed_at.isoformat(),
        "status": order.status.value,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }


@router.post(
    "/orders/{order_id}/cancel",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def cancel_pending_order(
    order_id: int,
    payload: EmployeeCancelOrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    order = await cancel_order(
        db=db,
        order=order,
        operator=current_user,
        note=payload.note or "employee canceled pending order",
    )
    await db.commit()
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
    }


@router.get("/aftersales", dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))])
async def list_aftersales(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: AfterSaleStatus | None = Query(default=None),
) -> list[dict]:
    stmt = (
        select(AfterSaleRequest)
        .where(AfterSaleRequest.deleted_at.is_(None))
        .order_by(desc(AfterSaleRequest.id))
        .limit(200)
    )
    if status is not None:
        stmt = stmt.where(AfterSaleRequest.status == status)
    rows = (await db.scalars(stmt)).all()
    order_ids = [row.order_id for row in rows]
    customer_ids = [row.customer_id for row in rows if row.customer_id]
    handler_ids = [row.handler_employee_id for row in rows if row.handler_employee_id]

    orders = (
        await db.scalars(select(Order).where(Order.id.in_(order_ids)))
    ).all() if order_ids else []
    order_map = {order.id: order for order in orders}

    users = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(customer_ids + handler_ids))
        )
    ).all() if customer_ids or handler_ids else []
    user_map = {user.id: user for user in users}

    result: list[dict] = []
    for row in rows:
        order = order_map.get(row.order_id)
        customer = user_map.get(row.customer_id)
        handler = user_map.get(row.handler_employee_id)
        result.append(
            {
                "id": row.id,
                "order_id": row.order_id,
                "order_no": order.order_no if order else None,
                "buyer_role": order.buyer_role.value if order else None,
                "customer_name": (
                    customer.profile.display_name
                    if customer and customer.profile and customer.profile.display_name
                    else (customer.username if customer else "unknown")
                ),
                "customer_phone": customer.profile.phone if customer and customer.profile else None,
                "reason": row.reason.value,
                "custom_reason_text": row.custom_reason_text,
                "process_type": row.process_type.value if row.process_type else None,
                "refund_amount": _amount_to_str(row.refund_amount) if row.refund_amount is not None else None,
                "chat_proof_url": row.chat_proof_url,
                "status": row.status.value,
                "note": row.customer_note or row.note,
                "customer_note": row.customer_note or row.note,
                "internal_note": row.internal_note,
                "handler_employee_id": row.handler_employee_id,
                "handler_name": (
                    handler.profile.display_name
                    if handler and handler.profile and handler.profile.display_name
                    else (handler.username if handler else None)
                ),
                "created_at": row.created_at.isoformat(),
            }
        )
    return result


@router.post(
    "/aftersales/{aftersale_id}/resolve",
    dependencies=[Depends(require_roles({UserRole.ADMIN, UserRole.EMPLOYEE}))],
)
async def resolve_aftersale(
    aftersale_id: int,
    payload: EmployeeResolveAfterSaleIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.get(AfterSaleRequest, aftersale_id)
    if not row or row.deleted_at:
        raise not_found("aftersale not found")
    order = await db.get(Order, row.order_id)
    if not order:
        raise not_found("order not found")

    before_status = row.status
    row.process_type = payload.process_type
    row.refund_amount = payload.refund_amount
    row.chat_proof_url = payload.chat_proof_url
    row.customer_note = (payload.customer_note or payload.note or "").strip() or None
    row.note = row.customer_note
    row.internal_note = (payload.internal_note or "").strip() or None
    row.handler_employee_id = current_user.id
    row.status = AfterSaleStatus.RESOLVED
    await write_business_event(
        db=db,
        entity_type="aftersale",
        entity_id=row.id,
        entity_no=f"AS{row.id}",
        action_code="aftersale.resolved",
        action_label="售后完结",
        source="employee",
        actor=current_user,
        before_data={"status": before_status.value},
        after_data={
            "status": row.status.value,
            "process_type": row.process_type.value if row.process_type else None,
            "refund_amount": f"{Decimal(row.refund_amount):.2f}" if row.refund_amount is not None else None,
            "handler_employee_id": row.handler_employee_id,
        },
        evidence={"chat_proof_url": row.chat_proof_url} if row.chat_proof_url else {},
        note=row.customer_note,
    )
    order.status = OrderStatus.CANCELED if payload.process_type != AfterSaleProcessType.EXCHANGE else order.status
    if order.status == OrderStatus.CANCELED:
        order.canceled_at = datetime.now(UTC)
        await write_business_event(
            db=db,
            entity_type="order",
            entity_id=order.id,
            entity_no=order.order_no,
            action_code="order.canceled",
            action_label="订单取消",
            source="employee",
            actor=current_user,
            after_data={"status": order.status.value, "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None},
            note=payload.note,
        )
    if row.customer_id:
        await create_customer_notification(
            db,
            user_id=row.customer_id,
            title="售后已处理",
            summary=f"售后单 AS{row.id} 已处理完成。",
            kind="aftersale",
            route="/pages/aftersale/list",
        )
    await db.commit()
    return {"id": row.id, "status": row.status.value, "order_status": order.status.value}
