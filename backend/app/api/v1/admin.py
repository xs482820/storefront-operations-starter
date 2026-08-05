from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from itertools import product as cartesian_product
import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.aftersale import AfterSaleRequest
from app.models.customer_runtime import CustomerAddress, CustomerCartItem
from app.models.customer_runtime import CustomerNotification
from app.models.enums import AfterSaleStatus, OrderStatus, PaymentStatus, SKUType, WholesaleApplicationStatus, UserRole
from app.models.order import Order, OrderItem
from app.models.payment import PaymentRecord
from app.models.product import OnlineStockLog, Product, ProductCategory, ProductSKU
from app.models.storefront import StorefrontMarqueeNotice
from app.models.image_generation import ImageGenerationHistory
from app.models.image_prompt_template import ImagePromptTemplate
from app.models.print_job import PrintJob
from app.models.user import CustomerProfile, User, WholesaleApplication
from app.schemas.admin import (
    BulkSkuCreateIn,
    ProductCategoryCreateIn,
    ProductCategoryUpdateIn,
    ProductCreateIn,
    ProductSkuSyncIn,
    StorefrontMarqueeNoticeIn,
    StorefrontMarqueeNoticeListIn,
    StorefrontMarqueeNoticeOut,
    ProductUpdateIn,
    SKUUpdateIn,
    UserRoleChangeIn,
    EmployeeAccountCreateIn,
    EmployeeAccountUpdateIn,
    DeleteConfirmationIn,
    AftersaleNotesIn,
    OrderAdjustmentIn,
    OrderTerminationIn,
    UserNoteUpdateIn,
    UserRuntimeStateUpdateIn,
    WholesaleApplicationReviewIn,
)
from app.schemas.auth import normalize_phone
from app.schemas.employee import EmployeeImagePromptTemplateIn
from app.services.events import write_business_event
from app.services.notifications import create_customer_notification
from app.services.inventory import set_online_stock
from app.services.ops_jobs import auto_cancel_expired_orders, auto_complete_shipped_orders
from app.services.orders import delete_order, mark_order_paid, terminate_order
from app.services.image_ai import test_store_image_service
from app.services.storefront_config import load_storefront_config, merge_storefront_config, public_storefront_config, STOREFRONT_CONFIG_PATH
from app.api.v1.employee import _serialize_image_history, _serialize_image_prompt_template

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
UPLOAD_ROOT = Path("/app/uploads/products")
UPLOAD_ROOT_FALLBACK = Path("uploads/products")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024

PAID_ORDER_STATUSES = (
    OrderStatus.AWAITING_SHIPMENT,
    OrderStatus.SHIPPED,
    OrderStatus.COMPLETED,
)


def _amount_to_str(value: Decimal | int | float | None) -> str:
    return f"{Decimal(value or 0):.2f}"


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


def _dump_image_urls(urls: list[str] | None) -> str:
    normalized = [str(item).strip() for item in (urls or []) if str(item).strip()]
    return json.dumps(normalized, ensure_ascii=False)


def _logical_sku_summary(skus: list[ProductSKU]) -> tuple[int, int, int]:
    logical_map: dict[tuple[str, str], int] = {}
    for sku in skus:
        if not sku.is_active:
            continue
        key = (sku.spec_value_1 or "", sku.spec_value_2 or "")
        logical_map[key] = max(logical_map.get(key, 0), sku.online_stock)
    logical_count = len(logical_map)
    total_stock = sum(logical_map.values())
    low_stock_count = sum(1 for qty in logical_map.values() if qty <= 10)
    return logical_count, total_stock, low_stock_count


@router.get("/product-categories", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_product_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    rows = (
        await db.scalars(
            select(ProductCategory).order_by(ProductCategory.sort_order.asc(), ProductCategory.id.asc())
        )
    ).all()
    counts = (
        await db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.category.is_not(None))
            .group_by(Product.category)
        )
    ).all()
    count_map = {name: int(total) for name, total in counts if name}
    return [
        {
            "id": row.id,
            "name": row.name,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
            "product_count": count_map.get(row.name, 0),
        }
        for row in rows
    ]


@router.post("/product-categories", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_product_category(
    payload: ProductCategoryCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    name = payload.name.strip()
    exists = await db.scalar(select(ProductCategory.id).where(ProductCategory.name == name))
    if exists:
        raise bad_request("category name already exists")
    row = ProductCategory(name=name, sort_order=payload.sort_order, is_active=payload.is_active)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
        "product_count": 0,
    }


@router.patch("/product-categories/{category_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_product_category(
    category_id: int,
    payload: ProductCategoryUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(ProductCategory, category_id)
    if not row:
        raise not_found("category not found")

    old_name = row.name
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        new_name = data["name"].strip()
        if not new_name:
            raise bad_request("category name is required")
        duplicate = await db.scalar(
            select(ProductCategory.id).where(ProductCategory.id != row.id, ProductCategory.name == new_name)
        )
        if duplicate:
            raise bad_request("category name already exists")
        row.name = new_name
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = data["sort_order"]
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]

    if row.name != old_name:
        await db.execute(
            sa.update(Product).where(Product.category == old_name).values(category=row.name)
        )

    await db.commit()
    linked_count = await db.scalar(select(func.count(Product.id)).where(Product.category == row.name)) or 0
    return {
        "id": row.id,
        "name": row.name,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
        "product_count": int(linked_count),
    }


@router.delete("/product-categories/{category_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_product_category(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(ProductCategory, category_id)
    if not row:
        raise not_found("category not found")
    await db.execute(
        sa.update(Product).where(Product.category == row.name).values(category=None)
    )
    await db.delete(row)
    await db.commit()
    return {"id": category_id, "deleted": True}


@router.post("/upload-image", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def upload_product_image(
    request: Request,
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
        "url": f"{base_url}/api/v1/admin/uploads/products/{saved_name}",
        "name": filename,
        "size": len(content),
    }


@router.get("/uploads/products/{file_name}")
async def get_uploaded_product_image(file_name: str) -> FileResponse:
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


@router.get("/dashboard", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    now = datetime.now(UTC)
    today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    today_end = datetime.combine(now.date(), time.max, tzinfo=UTC)
    trend_days = 15
    trend_start = today_start - timedelta(days=trend_days - 1)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)

    today_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.payable_amount), 0)).where(
            Order.paid_at.is_not(None),
            Order.paid_at >= today_start,
            Order.paid_at <= today_end,
        )
    )
    pending_order_count = await db.scalar(
        select(func.count(Order.id)).where(Order.status.in_([OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_SHIPMENT]))
    ) or 0
    active_product_count = await db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    pending_wholesale_count = await db.scalar(
        select(func.count(WholesaleApplication.id)).where(WholesaleApplication.status == WholesaleApplicationStatus.PENDING)
    ) or 0

    trend_rows = (
        await db.execute(
            select(
                func.date(Order.paid_at).label("day"),
                func.coalesce(func.sum(Order.payable_amount), 0).label("revenue"),
                func.count(Order.id).label("orders"),
            )
            .where(
                Order.paid_at.is_not(None),
                Order.paid_at >= trend_start,
                Order.paid_at <= today_end,
            )
            .group_by(func.date(Order.paid_at))
            .order_by(func.date(Order.paid_at).asc())
        )
    ).all()
    trend_by_day = {str(row.day): {"revenue": Decimal(row.revenue or 0), "orders": int(row.orders or 0)} for row in trend_rows}
    trend_points: list[dict] = []
    for offset in range(trend_days):
        day = trend_start.date() + timedelta(days=offset)
        item = trend_by_day.get(day.isoformat(), {"revenue": Decimal("0.00"), "orders": 0})
        trend_points.append(
            {
                "date": day.isoformat(),
                "revenue": _amount_to_str(item["revenue"]),
                "orders": item["orders"],
            }
        )

    revenue_mix_rows = (
        await db.execute(
            select(Order.buyer_role, func.coalesce(func.sum(Order.payable_amount), 0))
            .where(Order.paid_at.is_not(None), Order.paid_at >= month_start, Order.paid_at <= today_end)
            .group_by(Order.buyer_role)
        )
    ).all()
    revenue_mix = {row[0].value: Decimal(row[1] or 0) for row in revenue_mix_rows}

    order_mix_rows = (
        await db.execute(
            select(Order.buyer_role, func.count(Order.id))
            .where(Order.created_at >= month_start, Order.created_at <= today_end)
            .group_by(Order.buyer_role)
        )
    ).all()
    order_mix = {row[0].value: int(row[1] or 0) for row in order_mix_rows}

    async def _build_ranking(start_at: datetime) -> list[dict]:
        rows = (
            await db.execute(
                select(
                    OrderItem.product_name_snapshot,
                    func.coalesce(func.sum(OrderItem.quantity), 0).label("sales"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    Order.paid_at.is_not(None),
                    Order.paid_at >= start_at,
                    Order.status.in_(PAID_ORDER_STATUSES),
                )
                .group_by(OrderItem.product_name_snapshot)
                .order_by(desc("sales"))
                .limit(10)
            )
        ).all()
        if not rows:
            return []
        max_sales = max(int(row.sales or 0) for row in rows) or 1
        return [
            {
                "name": row.product_name_snapshot,
                "sales": int(row.sales or 0),
                "percent": int((int(row.sales or 0) / max_sales) * 100),
            }
            for row in rows
        ]

    pending_wholesale_order_count = await db.scalar(
        select(func.count(Order.id)).where(
            Order.status == OrderStatus.PENDING_PAYMENT,
            Order.buyer_role == UserRole.WHOLESALE,
        )
    ) or 0
    awaiting_shipment_count = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.AWAITING_SHIPMENT)
    ) or 0
    pending_aftersale_count = await db.scalar(
        select(func.count(AfterSaleRequest.id)).where(AfterSaleRequest.status == AfterSaleStatus.PENDING, AfterSaleRequest.deleted_at.is_(None))
    ) or 0
    low_stock_count = await db.scalar(
        select(func.count(ProductSKU.id)).where(ProductSKU.is_active.is_(True), ProductSKU.online_stock <= 10)
    ) or 0
    draft_product_count = await db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(False))) or 0

    recent_orders = (
        await db.scalars(
            select(Order)
            .where(Order.status.in_([OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_SHIPMENT, OrderStatus.SHIPPED]))
            .order_by(desc(Order.id))
            .limit(5)
        )
    ).all()
    recent_order_ids = [row.id for row in recent_orders]
    customer_ids = [row.customer_id for row in recent_orders if row.customer_id]
    users = (
        await db.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id.in_(customer_ids))
        )
    ).all() if customer_ids else []
    user_map = {user.id: user for user in users}
    order_items = (
        await db.scalars(select(OrderItem).where(OrderItem.order_id.in_(recent_order_ids)))
    ).all() if recent_order_ids else []
    first_line_by_order: dict[int, OrderItem] = {}
    for item in order_items:
        first_line_by_order.setdefault(item.order_id, item)

    alert_skus = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.is_active.is_(True), ProductSKU.online_stock <= 10)
            .order_by(ProductSKU.online_stock.asc(), ProductSKU.id.desc())
            .limit(6)
        )
    ).all()

    return {
        "snapshot": {
            "today_revenue": _amount_to_str(today_revenue),
            "pending_order_count": int(pending_order_count),
            "active_product_count": int(active_product_count),
            "pending_wholesale_count": int(pending_wholesale_count),
        },
        "trend": {
            "days": trend_days,
            "points": trend_points,
        },
        "customer_mix": {
            "revenue": [
                {"name": "wholesale", "value": _amount_to_str(revenue_mix.get(UserRole.WHOLESALE.value))},
                {"name": "retail", "value": _amount_to_str(revenue_mix.get(UserRole.RETAIL.value))},
            ],
            "orders": [
                {"name": "wholesale", "value": int(order_mix.get(UserRole.WHOLESALE.value, 0))},
                {"name": "retail", "value": int(order_mix.get(UserRole.RETAIL.value, 0))},
            ],
        },
        "rankings": {
            "week": await _build_ranking(week_start),
            "month": await _build_ranking(month_start),
        },
        "tasks": {
            "urgent": [
                {
                    "id": "wholesale-payment",
                    "title": f"待确认批发收款 {pending_wholesale_order_count} 单",
                    "desc": "线下转账订单需先确认收款，再进入发货流程。",
                    "time": "今日",
                    "path": "/orders",
                    "count": int(pending_wholesale_order_count),
                },
                {
                    "id": "awaiting-shipment",
                    "title": f"待发货订单 {awaiting_shipment_count} 单",
                    "desc": "已付款订单等待出库处理，请尽快完成配货与发货。",
                    "time": "今日",
                    "path": "/orders",
                    "count": int(awaiting_shipment_count),
                },
                {
                    "id": "wholesale-review",
                    "title": f"待审核批发申请 {pending_wholesale_count} 个",
                    "desc": "通过审核后，客户可查看批发价格并按批发规则下单。",
                    "time": "今日",
                    "path": "/users",
                    "count": int(pending_wholesale_count),
                },
                {
                    "id": "pending-aftersale",
                    "title": f"待处理售后 {pending_aftersale_count} 单",
                    "desc": "微信沟通已结束的售后，仍需在系统补录处理结果。",
                    "time": "今日",
                    "path": "/aftersales",
                    "count": int(pending_aftersale_count),
                },
            ],
            "follow": [
                {
                    "id": "low-stock",
                    "title": f"低库存 SKU {low_stock_count} 个",
                    "desc": "线上库存接近售空，建议尽快补充可售库存池。",
                    "time": "持续",
                    "path": "/products",
                    "count": int(low_stock_count),
                },
                {
                    "id": "draft-products",
                    "title": f"待完善商品 {draft_product_count} 个",
                    "desc": "存在未上架或信息不完整的商品，建议尽快补齐后发布。",
                    "time": "持续",
                    "path": "/products",
                    "count": int(draft_product_count),
                },
            ],
        },
        "recent_orders": [
            {
                "order_id": row.id,
                "order_no": row.order_no,
                "customer_name": (
                    user_map[row.customer_id].profile.display_name
                    if row.customer_id and row.customer_id in user_map and user_map[row.customer_id].profile and user_map[row.customer_id].profile.display_name
                    else (user_map[row.customer_id].username if row.customer_id and row.customer_id in user_map else "unknown")
                ),
                "identity": row.buyer_role.value,
                "status": row.status.value,
                "payment_method": row.payment_method.value,
                "amount": _amount_to_str(row.payable_amount),
                "item_summary": first_line_by_order[row.id].product_name_snapshot if row.id in first_line_by_order else None,
            }
            for row in recent_orders
        ],
        "stock_alerts": [
            {
                "sku_id": sku.id,
                "product_name": sku.product.name if sku.product else sku.sku_code,
                "spec": sku.sku_label or "/".join(filter(None, [sku.spec_value_1, sku.spec_value_2])),
                "stock": sku.online_stock,
            }
            for sku in alert_skus
        ],
    }


@router.post("/products", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_product(
    payload: ProductCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    exists = await db.scalar(select(Product.id).where(Product.product_code == payload.product_code))
    if exists:
        raise bad_request("product_code already exists")
    product_data = payload.model_dump()
    product_data["image_urls"] = _dump_image_urls(payload.image_urls)
    row = Product(**product_data)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "product_code": row.product_code}


@router.get("/products", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[dict]:
    stmt = select(Product).options(selectinload(Product.skus)).order_by(desc(Product.id))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(like_kw), Product.model_name.ilike(like_kw), Product.product_code.ilike(like_kw)))
    rows = (await db.scalars(stmt)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "model_name": row.model_name,
            "product_code": row.product_code,
            "category": row.category,
            "image_urls": _parse_image_urls(row.image_urls),
            "supports_retail": row.supports_retail,
            "supports_wholesale": row.supports_wholesale,
            "has_dual_price": row.has_dual_price,
            "is_active": row.is_active,
            "sku_count": _logical_sku_summary(row.skus)[0],
            "total_online_stock": _logical_sku_summary(row.skus)[1],
            "low_stock_sku_count": _logical_sku_summary(row.skus)[2],
            "price_mode": (
                "dual_price"
                if row.has_dual_price and row.supports_wholesale
                else ("retail_only" if row.supports_retail and not row.supports_wholesale else "wholesale_only")
            ),
        }
        for row in rows
    ]


@router.get("/products/{product_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_product_detail(
    product_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.scalar(select(Product).options(selectinload(Product.skus)).where(Product.id == product_id))
    if not row:
        raise not_found("product not found")
    skus = sorted(
        row.skus,
        key=lambda x: (x.sku_type.value, x.spec_value_1 or "", x.spec_value_2 or "", x.id),
    )
    logical_count, total_stock, _ = _logical_sku_summary(skus)
    return {
        "id": row.id,
        "name": row.name,
        "model_name": row.model_name,
        "product_code": row.product_code,
        "brand": row.brand,
        "category": row.category,
        "image_urls": _parse_image_urls(row.image_urls),
        "description": row.description,
        "spec_dim_1_name": row.spec_dim_1_name,
        "spec_dim_2_name": row.spec_dim_2_name,
        "supports_retail": row.supports_retail,
        "supports_wholesale": row.supports_wholesale,
        "has_dual_price": row.has_dual_price,
        "is_active": row.is_active,
        "sku_count": logical_count,
        "total_online_stock": total_stock,
        "skus": [
            {
                "id": sku.id,
                "sku_code": sku.sku_code,
                "sku_type": sku.sku_type.value,
                "spec_value_1": sku.spec_value_1,
                "spec_value_2": sku.spec_value_2,
                "sku_label": sku.sku_label,
                "is_mixed_pack": sku.is_mixed_pack,
                "mixed_pack_note": sku.mixed_pack_note,
                "online_stock": sku.online_stock,
                "retail_price": _amount_to_str(sku.retail_price),
                "wholesale_price": _amount_to_str(sku.wholesale_price),
                "min_sale_qty": sku.min_sale_qty,
                "min_wholesale_qty": sku.min_wholesale_qty,
                "is_active": sku.is_active,
            }
            for sku in skus
        ],
    }


@router.patch("/products/{product_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(Product, product_id)
    if not row:
        raise not_found("product not found")
    data = payload.model_dump(exclude_unset=True)
    if "image_urls" in data:
        data["image_urls"] = _dump_image_urls(data["image_urls"])
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    return {"id": row.id, "updated": True}


@router.post("/products/bulk-sku", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def bulk_create_skus(
    payload: BulkSkuCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    product_row = await db.get(Product, payload.product_id)
    if not product_row:
        raise not_found("product not found")
    created = 0
    for value_1, value_2 in cartesian_product(payload.spec_values_1, payload.spec_values_2):
        spec_1 = value_1.strip()
        spec_2 = value_2.strip()
        existing = await db.scalar(
            select(ProductSKU.id).where(
                ProductSKU.product_id == payload.product_id,
                ProductSKU.sku_type == payload.sku_type,
                ProductSKU.spec_value_1 == spec_1,
                ProductSKU.spec_value_2 == spec_2,
            )
        )
        if existing:
            continue
        sku = ProductSKU(
            product_id=payload.product_id,
            sku_code=f"{product_row.product_code}-{payload.sku_type.value[:1].upper()}-{created + 1:03d}-{abs(hash((spec_1, spec_2))) % 1000:03d}",
            sku_type=payload.sku_type,
            spec_value_1=spec_1,
            spec_value_2=spec_2,
            sku_label=f"{spec_1}/{spec_2}",
            is_mixed_pack=payload.is_mixed_pack,
            mixed_pack_note=payload.mixed_pack_note,
            online_stock=payload.online_stock,
            retail_price=payload.retail_price,
            wholesale_price=payload.wholesale_price,
            min_sale_qty=payload.min_sale_qty,
            min_wholesale_qty=payload.min_wholesale_qty,
        )
        db.add(sku)
        await db.flush()
        created += 1
    await db.commit()
    return {"product_id": payload.product_id, "created": created}


@router.post("/products/sync-skus", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def sync_product_skus(
    payload: ProductSkuSyncIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    product_row = await db.get(Product, payload.product_id)
    if not product_row:
        raise not_found("product not found")

    # 1. 获取当前所�?SKU
    existing_skus = (await db.scalars(
        select(ProductSKU).where(ProductSKU.product_id == payload.product_id)
    )).all()

    # 2. 准备同步数据
    # 我们需要确保零售和批发 SKU 都存�?    desired_matrix = []
    for row in payload.skus:
        spec_1 = row.spec_value_1.strip() or "默认"
        spec_2 = row.spec_value_2.strip() or "默认"
        desired_matrix.append({
            "spec_1": spec_1,
            "spec_2": spec_2,
            "retail_price": row.retail_price,
            "wholesale_price": row.wholesale_price,
            "min_wholesale_qty": row.min_wholesale_qty,
            "online_stock": row.online_stock,
        })

    # 3. 确保所有需要的 SKU 记录都存�?    sku_map = {(s.sku_type, s.spec_value_1, s.spec_value_2): s for s in existing_skus}
    
    # 记录哪些 SKU 需要保持激�?    active_keys = set()

    for item in desired_matrix:
        for sku_type in [SKUType.RETAIL, SKUType.WHOLESALE]:
            key = (sku_type, item["spec_1"], item["spec_2"])
            active_keys.add(key)
            
            if key not in sku_map:
                # 创建缺失�?SKU
                new_sku = ProductSKU(
                    product_id=payload.product_id,
                    sku_code=f"{product_row.product_code}-{sku_type.value[:1].upper()}-{len(sku_map) + 1:03d}",
                    sku_type=sku_type,
                    spec_value_1=item["spec_1"],
                    spec_value_2=item["spec_2"],
                    sku_label=f"{item['spec_1']}/{item['spec_2']}",
                    online_stock=item["online_stock"],
                    retail_price=item["retail_price"],
                    wholesale_price=item["wholesale_price"],
                    min_sale_qty=1,
                    min_wholesale_qty=item["min_wholesale_qty"],
                    is_active=True
                )
                db.add(new_sku)
                sku_map[key] = new_sku
            else:
                # 更新现有�?SKU
                sku = sku_map[key]
                sku.online_stock = item["online_stock"]
                sku.retail_price = item["retail_price"]
                sku.wholesale_price = item["wholesale_price"]
                sku.min_wholesale_qty = item["min_wholesale_qty"]
                sku.is_active = True

    # 4. 禁用不在矩阵中的 SKU
    for key, sku in sku_map.items():
        if key not in active_keys:
            sku.is_active = False
            sku.online_stock = 0

    await db.commit()
    return {"product_id": payload.product_id, "synced": len(desired_matrix)}


@router.patch("/skus/{sku_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_sku(
    sku_id: int,
    payload: SKUUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    sku = await db.get(ProductSKU, sku_id)
    if not sku:
        raise not_found("sku not found")
    data = payload.model_dump(exclude_unset=True)
    if "online_stock" in data:
        target_qty = data.pop("online_stock")
        await set_online_stock(db=db, sku_id=sku.id, target_qty=target_qty, operator=current_user, note="admin update sku stock")
    for key, value in data.items():
        setattr(sku, key, value)
    await db.commit()
    return {"sku_id": sku.id, "updated": True, "online_stock": sku.online_stock}


@router.get("/skus/{sku_id}/stock-logs", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_sku_stock_logs(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    sku = await db.get(ProductSKU, sku_id)
    if not sku:
        raise not_found("sku not found")
    rows = (
        await db.scalars(
            select(OnlineStockLog)
            .where(OnlineStockLog.sku_id == sku_id)
            .order_by(desc(OnlineStockLog.id))
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": row.id,
            "delta_qty": row.delta_qty,
            "before_qty": row.before_qty,
            "after_qty": row.after_qty,
            "reason": row.reason.value,
            "ref_order_no": row.ref_order_no,
            "operator_user_id": row.operator_user_id,
            "note": row.note,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/wholesale-applications", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_wholesale_applications(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    rows = (
        await db.execute(
            select(WholesaleApplication, User.username)
            .join(User, User.id == WholesaleApplication.user_id)
            .order_by(desc(WholesaleApplication.id))
            .limit(200)
        )
    ).all()
    return [
        {
            "id": row.id,
            "username": username,
            "status": row.status.value,
            "company_name": row.company_name,
            "store_name": row.store_name,
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
            "business_license_url": row.business_license_url,
            "remark": row.remark,
            "review_note": row.review_note,
            "created_at": row.created_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        }
        for row, username in rows
    ]


@router.get("/users", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    role: UserRole | None = Query(default=None),
    application_status: WholesaleApplicationStatus | None = Query(default=None),
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[dict]:
    stmt = select(User).options(selectinload(User.profile)).where(User.deleted_at.is_(None)).order_by(desc(User.id))
    if role:
        stmt = stmt.where(User.role == role)
    else:
        stmt = stmt.where(User.role.in_([UserRole.RETAIL, UserRole.WHOLESALE]))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = (
            stmt.outerjoin(CustomerProfile, CustomerProfile.user_id == User.id)
            .where(
                or_(
                    User.username.ilike(like_kw),
                    CustomerProfile.phone.ilike(like_kw),
                    CustomerProfile.display_name.ilike(like_kw),
                    CustomerProfile.company_name.ilike(like_kw),
                    CustomerProfile.store_name.ilike(like_kw),
                )
            )
        )
    rows = (await db.scalars(stmt)).all()
    user_ids = [row.id for row in rows]

    order_count_rows = (
        await db.execute(
            select(Order.customer_id, func.count(Order.id))
            .where(Order.customer_id.in_(user_ids))
            .group_by(Order.customer_id)
        )
    ).all() if user_ids else []
    order_count_map = {int(user_id): int(count) for user_id, count in order_count_rows if user_id is not None}

    application_rows = (
        await db.scalars(
            select(WholesaleApplication)
            .where(WholesaleApplication.user_id.in_(user_ids))
            .order_by(WholesaleApplication.user_id.asc(), WholesaleApplication.id.desc())
        )
    ).all() if user_ids else []
    latest_application_by_user: dict[int, WholesaleApplication] = {}
    for row in application_rows:
        latest_application_by_user.setdefault(row.user_id, row)

    result = [
        {
            "id": row.id,
            "username": row.username,
            "role": row.role.value,
            "is_active": row.is_active,
            "is_blacklisted": row.is_blacklisted,
            "is_flagged": row.is_flagged,
            "display_name": row.profile.display_name if row.profile else None,
            "phone": row.profile.phone if row.profile else None,
            "company_name": row.profile.company_name if row.profile else None,
            "store_name": row.profile.store_name if row.profile else None,
            "is_verified_wholesale": bool(row.profile.is_verified_wholesale) if row.profile else False,
            "created_at": row.created_at.isoformat(),
            "order_count": order_count_map.get(row.id, 0),
            "latest_application_id": latest_application_by_user[row.id].id if row.id in latest_application_by_user else None,
            "application_status": latest_application_by_user[row.id].status.value if row.id in latest_application_by_user else None,
            "application_remark": latest_application_by_user[row.id].remark if row.id in latest_application_by_user else None,
            "application_review_note": latest_application_by_user[row.id].review_note if row.id in latest_application_by_user else None,
        }
        for row in rows
    ]
    if application_status is not None:
        result = [item for item in result if item.get("application_status") == application_status.value]
    return result


@router.patch("/users/{user_id}/role", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_user_role(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    role: UserRole = Query(...),
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    before_role = user.role
    user.role = role
    user.session_version += 1
    if user.profile:
        user.profile.is_verified_wholesale = role == UserRole.WHOLESALE
    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="user.role.updated",
        action_label="用户角色更新",
        source="admin",
        actor=current_user,
        before_data={"role": before_role.value},
        after_data={
            "role": user.role.value,
            "is_verified_wholesale": bool(user.profile.is_verified_wholesale) if user.profile else False,
        },
    )
    await db.commit()
    return {"id": user.id, "role": user.role.value}


@router.post("/users/{user_id}/role-change", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_user_role_secure(
    user_id: int,
    payload: UserRoleChangeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    if user.role == UserRole.ADMIN:
        raise bad_request("cannot change admin account role")
    if payload.role == UserRole.ADMIN:
        raise bad_request("cannot assign admin role")

    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()

    next_role = payload.role
    before_role = user.role
    if next_role == UserRole.EMPLOYEE:
        if not verify_password((payload.admin_confirm_password or "").strip(), current_user.password_hash):
            raise bad_request("admin confirm password invalid")
        raw_contact_phone = (payload.contact_phone or "").strip()
        try:
            normalized_contact_phone = normalize_phone(raw_contact_phone)
        except ValueError as exc:
            raise bad_request(str(exc)) from exc

        if user.profile.phone and user.profile.phone != normalized_contact_phone:
            raise bad_request("contact_phone does not match current bound phone")
        user.profile.phone = normalized_contact_phone
        user.profile.is_verified_wholesale = False
    elif next_role == UserRole.WHOLESALE:
        raw_contact_phone = (payload.contact_phone or "").strip()
        try:
            normalized_contact_phone = normalize_phone(raw_contact_phone)
        except ValueError as exc:
            raise bad_request(str(exc)) from exc

        user.profile.company_name = (payload.company_name or "").strip() or user.profile.company_name
        user.profile.store_name = (payload.store_name or "").strip() or user.profile.store_name
        user.profile.contact_name = (payload.contact_name or "").strip() or user.profile.contact_name
        user.profile.phone = normalized_contact_phone or user.profile.phone
        user.profile.address = (payload.address or "").strip() or user.profile.address
        user.profile.business_license_url = (
            (payload.business_license_url or "").strip() or user.profile.business_license_url
        )
        user.profile.is_verified_wholesale = True
        db.add(
            WholesaleApplication(
                user_id=user.id,
                status=WholesaleApplicationStatus.APPROVED,
                company_name=(payload.company_name or "").strip() or None,
                store_name=(payload.store_name or "").strip() or None,
                contact_name=(payload.contact_name or "").strip() or None,
                contact_phone=normalized_contact_phone,
                business_license_url=(payload.business_license_url or "").strip() or None,
                remark=(payload.business_type or "").strip() or None,
                review_note="admin role change",
                reviewed_by=current_user.id,
                reviewed_at=datetime.now(UTC),
            )
        )
    else:
        # Downgrade to retail: keep historical wholesale fields, only revoke wholesale verification.
        user.profile.is_verified_wholesale = False

    user.role = next_role
    user.session_version += 1
    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="user.role.changed",
        action_label="用户角色切换",
        source="admin",
        actor=current_user,
        before_data={"role": before_role.value},
        after_data={
            "role": user.role.value,
            "is_verified_wholesale": bool(user.profile.is_verified_wholesale) if user.profile else False,
        },
        note=(payload.business_type or "").strip() or None,
    )
    await db.commit()
    return {
        "id": user.id,
        "role": user.role.value,
        "is_verified_wholesale": bool(user.profile.is_verified_wholesale),
    }


@router.post("/employee-accounts", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_employee_account(
    payload: EmployeeAccountCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if not verify_password(payload.admin_confirm_password.strip(), current_user.password_hash):
        raise bad_request("admin confirm password invalid")
    username = payload.username.strip()
    if await db.scalar(select(User.id).where(User.username == username)):
        raise bad_request("username already exists")
    user = User(username=username, password_hash=get_password_hash(payload.password), role=UserRole.EMPLOYEE, is_active=True)
    db.add(user)
    await db.flush()
    db.add(CustomerProfile(user_id=user.id, display_name=(payload.display_name or "").strip() or username))
    await write_business_event(
        db=db, entity_type="user", entity_id=user.id, entity_no=user.username,
        action_code="employee.account.created", action_label="店员账号创建", source="admin", actor=current_user,
        after_data={"role": user.role.value, "is_active": True},
    )
    await db.commit()
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.patch("/users/{user_id}/employee-account", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_employee_account(
    user_id: int, payload: EmployeeAccountUpdateIn, db: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.get(User, user_id)
    if not user or user.role != UserRole.EMPLOYEE:
        raise bad_request("user is not an employee")
    if not verify_password(payload.admin_confirm_password.strip(), current_user.password_hash):
        raise bad_request("admin confirm password invalid")
    before = {"username": user.username, "is_active": user.is_active}
    if payload.username and payload.username.strip() != user.username:
        username = payload.username.strip()
        if await db.scalar(select(User.id).where(User.username == username, User.id != user.id)):
            raise bad_request("username already exists")
        user.username = username
    if payload.password:
        user.password_hash = get_password_hash(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password or payload.is_active is False:
        user.session_version += 1
    await write_business_event(db=db, entity_type="user", entity_id=user.id, entity_no=user.username, action_code="employee.account.updated", action_label="店员账号更新", source="admin", actor=current_user, before_data=before, after_data={"username": user.username, "is_active": user.is_active, "password_reset": bool(payload.password)})
    await db.commit()
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


@router.delete("/users/{user_id}/employee-account", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_employee_account(
    user_id: int,
    payload: DeleteConfirmationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.confirmation_text.strip() != "确认删除此账号":
        raise bad_request("confirmation text does not match")
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user or user.role != UserRole.EMPLOYEE or user.deleted_at:
        raise not_found("employee account not found")
    before = {
        "username": user.username,
        "display_name": user.profile.display_name if user.profile else None,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    user.is_active = False
    user.session_version += 1
    user.deleted_at = datetime.now(UTC)
    user.deleted_by_user_id = current_user.id
    await write_business_event(
        db=db, entity_type="employee_account", entity_id=user.id, entity_no=user.username,
        action_code="employee.account.deleted", action_label="删除工作台账号", source="admin", actor=current_user,
        before_data=before,
        after_data={"is_active": False, "deleted_at": user.deleted_at.isoformat()},
    )
    await db.commit()
    return {"id": user.id, "deleted": True}


@router.patch("/users/{user_id}/runtime-state", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_user_runtime_state(
    user_id: int,
    payload: UserRuntimeStateUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    if payload.is_blacklisted is None and payload.is_flagged is None:
        raise bad_request("at least one field is required")

    before_state = {"is_blacklisted": user.is_blacklisted, "is_flagged": user.is_flagged}
    if payload.is_blacklisted is not None:
        if user.role in {UserRole.ADMIN, UserRole.EMPLOYEE} and payload.is_blacklisted:
            raise bad_request("cannot blacklist admin or employee account")
        user.is_blacklisted = payload.is_blacklisted
    if payload.is_flagged is not None:
        user.is_flagged = payload.is_flagged

    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="user.runtime_state.updated",
        action_label="用户状态更新",
        source="admin",
        actor=current_user,
        before_data=before_state,
        after_data={"is_blacklisted": user.is_blacklisted, "is_flagged": user.is_flagged},
    )
    await db.commit()
    return {
        "id": user.id,
        "is_blacklisted": user.is_blacklisted,
        "is_flagged": user.is_flagged,
    }


@router.get("/users/{user_id}/customer-360", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_customer_360(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")

    profile = user.profile
    location = None
    if profile:
        location = profile.address or profile.store_name or profile.company_name

    total_spent = await db.scalar(
        select(func.coalesce(func.sum(Order.payable_amount), 0))
        .where(Order.customer_id == user_id, Order.paid_at.is_not(None))
    ) or Decimal("0")
    total_orders = await db.scalar(select(func.count(Order.id)).where(Order.customer_id == user_id)) or 0
    last_order_time = await db.scalar(
        select(func.max(Order.created_at)).where(Order.customer_id == user_id)
    )

    latest_application = await db.scalar(
        select(WholesaleApplication)
        .where(WholesaleApplication.user_id == user_id)
        .order_by(desc(WholesaleApplication.id))
        .limit(1)
    )

    recent_orders = (
        await db.scalars(
            select(Order)
            .where(Order.customer_id == user_id)
            .order_by(desc(Order.id))
            .limit(10)
        )
    ).all()

    order_ids = [row.id for row in recent_orders]
    recent_aftersales = (
        await db.scalars(
            select(AfterSaleRequest)
            .where(AfterSaleRequest.customer_id == user_id, AfterSaleRequest.deleted_at.is_(None))
            .order_by(desc(AfterSaleRequest.id))
            .limit(10)
        )
    ).all()
    related_order_ids = list({row.order_id for row in recent_aftersales if row.order_id})

    order_map_rows = (
        await db.scalars(
            select(Order).where(Order.id.in_(related_order_ids))
        )
    ).all() if related_order_ids else []
    order_map = {row.id: row for row in order_map_rows}

    cart_rows = (
        await db.execute(
            select(CustomerCartItem, ProductSKU, Product)
            .join(ProductSKU, ProductSKU.id == CustomerCartItem.sku_id)
            .join(Product, Product.id == ProductSKU.product_id)
            .where(CustomerCartItem.user_id == user_id)
            .order_by(desc(CustomerCartItem.id))
        )
    ).all()
    address_rows = (
        await db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user_id)
            .order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.id))
        )
    ).all()
    notification_rows = (
        await db.scalars(
            select(CustomerNotification)
            .where(CustomerNotification.user_id == user_id)
            .order_by(desc(CustomerNotification.id))
            .limit(30)
        )
    ).all()
    storefront_config = load_storefront_config()
    notification_label_map = {
        str(item.get("key", "")).strip(): str(item.get("label", "")).strip()
        for item in (storefront_config.get("notification_settings", {}) or {})
        .get("miniapp_subscribe", {})
        .get("events", [])
        if isinstance(item, dict)
        and str(item.get("key", "")).strip()
        and str(item.get("label", "")).strip()
    }
    notification_event_keys = list(profile.miniapp_notification_event_keys or []) if profile else []
    notification_event_labels = [
        notification_label_map.get(key, key)
        for key in notification_event_keys
        if notification_label_map.get(key, key)
    ]

    is_wholesale_user = user.role == UserRole.WHOLESALE

    return {
        "id": user.id,
        "current_role": user.role.value,
        "name": (
            profile.display_name
            if profile and profile.display_name
            else user.username
        ),
        "type": "wholesale" if user.role == UserRole.WHOLESALE else "retail",
        "phone": profile.phone if profile else None,
        "company_name": profile.company_name if profile else None,
        "store_name": profile.store_name if profile else None,
        "contact_name": profile.contact_name if profile else None,
        "address": profile.address if profile else None,
        "business_license_url": profile.business_license_url if profile else None,
        "location": location,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "miniapp_notification_enabled": bool(profile.miniapp_notification_enabled) if profile else False,
        "miniapp_notification_event_keys": notification_event_keys,
        "miniapp_notification_event_labels": notification_event_labels,
        "miniapp_notification_updated_at": (
            profile.miniapp_notification_updated_at.isoformat()
            if profile and profile.miniapp_notification_updated_at
            else None
        ),
        "default_receiver": (
            f"{profile.contact_name or ''} {profile.phone or ''}".strip()
            if profile
            else None
        ),
        "total_spent": _amount_to_str(total_spent),
        "total_orders": int(total_orders),
        "last_order_time": last_order_time.isoformat() if last_order_time else None,
        "business_type": (
            (profile.company_name or profile.store_name)
            if profile
            else None
        ),
        "apply_note": latest_application.remark if latest_application else None,
        "note": profile.note if profile else None,
        "orders": [
            {
                "order_no": row.order_no,
                "created_at": row.created_at.isoformat(),
                "amount": _amount_to_str(row.payable_amount),
                "status": row.status.value,
            }
            for row in recent_orders
        ],
        "aftersales": [
            {
                "id": row.id,
                "order_no": order_map[row.order_id].order_no if row.order_id in order_map else None,
                "type": row.reason.value,
                "refund_amount": _amount_to_str(row.refund_amount),
                "status": row.status.value,
                "created_at": row.created_at.isoformat(),
            }
            for row in recent_aftersales
        ],
        "cart_items": [
            {
                "id": cart.id,
                "sku_id": sku.id,
                "sku_code": sku.sku_code,
                "product_name": product.name,
                "spec_text": sku.sku_label or "/".join(filter(None, [sku.spec_value_1, sku.spec_value_2])) or "默认规格",
                "quantity": cart.quantity,
                "selected": cart.selected,
                "unit_price": _amount_to_str(sku.wholesale_price if is_wholesale_user else sku.retail_price),
                "created_at": cart.created_at.isoformat() if cart.created_at else None,
            }
            for cart, sku, product in cart_rows
        ],
        "addresses": [
            {
                "id": row.id,
                "contact_name": row.contact_name,
                "phone": row.phone,
                "region": row.region,
                "detail": row.detail,
                "tag": row.tag,
                "is_default": row.is_default,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in address_rows
        ],
        "notifications": [
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "kind": row.kind,
                "route": row.route,
                "unread": row.unread,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in notification_rows
        ],
    }


@router.get("/storefront-config", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_storefront_config() -> dict:
    return load_storefront_config()


@router.get("/image-ai/history", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_image_ai_history(db: Annotated[AsyncSession, Depends(get_db)]) -> list[dict]:
    rows = (await db.execute(
        select(ImageGenerationHistory, User.username)
        .join(User, User.id == ImageGenerationHistory.user_id)
        .order_by(desc(ImageGenerationHistory.id))
        .limit(100)
    )).all()
    return [_serialize_image_history(row, username=username) for row, username in rows]


@router.post("/image-ai/connection-test", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def test_image_ai_connection() -> dict:
    settings = load_storefront_config(include_secrets=True).get("image_ai_settings") or {}
    return await test_store_image_service(settings=settings)


@router.get("/image-ai/templates", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_image_ai_templates(db: Annotated[AsyncSession, Depends(get_db)]) -> list[dict]:
    rows = (await db.execute(
        select(ImagePromptTemplate, User.username)
        .outerjoin(User, User.id == ImagePromptTemplate.owner_user_id)
        .order_by(desc(ImagePromptTemplate.is_shared), desc(ImagePromptTemplate.id))
    )).all()
    return [_serialize_image_prompt_template(row, username=username) for row, username in rows]


@router.post("/image-ai/templates", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_image_ai_template(payload: EmployeeImagePromptTemplateIn, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    row = ImagePromptTemplate(name=payload.name.strip(), prompt=payload.prompt.strip(), is_shared=True)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_image_prompt_template(row)


@router.patch("/image-ai/templates/{template_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_image_ai_template(template_id: int, payload: EmployeeImagePromptTemplateIn, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    row = await db.get(ImagePromptTemplate, template_id)
    if not row:
        raise not_found("prompt template not found")
    row.name, row.prompt = payload.name.strip(), payload.prompt.strip()
    await db.commit()
    return _serialize_image_prompt_template(row)


@router.delete("/image-ai/templates/{template_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_image_ai_template(template_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    row = await db.get(ImagePromptTemplate, template_id)
    if not row:
        raise not_found("prompt template not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.put("/storefront-config", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_storefront_config(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    previous = None
    if STOREFRONT_CONFIG_PATH.exists():
        try:
            previous = json.loads(STOREFRONT_CONFIG_PATH.read_text(encoding="utf-8") or "{}")
        except Exception:
            previous = None
    result = merge_storefront_config(previous, payload)
    STOREFRONT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    STOREFRONT_CONFIG_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    await write_business_event(
        db=db,
        entity_type="storefront_config",
        entity_id=None,
        entity_no="storefront-config",
        action_code="storefront.updated",
        action_label="店面设置更新",
        source="admin",
        actor=current_user,
        before_data=public_storefront_config(previous or {}),
        after_data=public_storefront_config(result),
    )
    return public_storefront_config(result)


def _parse_optional_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _serialize_marquee_notice(row: StorefrontMarqueeNotice) -> StorefrontMarqueeNoticeOut:
    return StorefrontMarqueeNoticeOut(
        id=row.id,
        title=row.title,
        body=row.body,
        action_label=row.action_label,
        action_type=row.action_type,
        action_value=row.action_value,
        is_active=bool(row.is_active),
        sort_order=row.sort_order,
        starts_at=row.starts_at.isoformat() if row.starts_at else None,
        ends_at=row.ends_at.isoformat() if row.ends_at else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.get(
    "/storefront-marquee-notices",
    response_model=list[StorefrontMarqueeNoticeOut],
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)


async def list_storefront_marquee_notices(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StorefrontMarqueeNoticeOut]:
    rows = (
        await db.execute(
            select(StorefrontMarqueeNotice)
            .order_by(StorefrontMarqueeNotice.sort_order.asc(), StorefrontMarqueeNotice.id.asc())
        )
    ).scalars().all()
    return [_serialize_marquee_notice(row) for row in rows]


@router.put(
    "/storefront-marquee-notices",
    response_model=list[StorefrontMarqueeNoticeOut],
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def replace_storefront_marquee_notices(
    payload: StorefrontMarqueeNoticeListIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[StorefrontMarqueeNoticeOut]:
    before_rows = (
        await db.execute(
            select(StorefrontMarqueeNotice)
            .order_by(StorefrontMarqueeNotice.sort_order.asc(), StorefrontMarqueeNotice.id.asc())
        )
    ).scalars().all()
    before_data = [item.model_dump() for item in [_serialize_marquee_notice(row) for row in before_rows]]
    for row in before_rows:
        await db.delete(row)
    await db.flush()
    next_rows: list[StorefrontMarqueeNotice] = []
    for item in payload.notices:
        row = StorefrontMarqueeNotice(
            title=item.title.strip(),
            body=(item.body or "").strip(),
            action_label=item.action_label.strip() or "查看",
            action_type=(item.action_type or "none").strip() or "none",
            action_value=(item.action_value or "").strip() or None,
            is_active=item.is_active,
            sort_order=item.sort_order,
            starts_at=_parse_optional_dt(item.starts_at),
            ends_at=_parse_optional_dt(item.ends_at),
        )
        db.add(row)
        next_rows.append(row)
    await db.flush()
    after_data = [item.model_dump() for item in [_serialize_marquee_notice(row) for row in next_rows]]
    await write_business_event(
        db=db,
        entity_type="storefront_config",
        entity_id=None,
        entity_no="storefront-marquee-notices",
        action_code="storefront.marquee_notices.updated",
        action_label="跑马灯公告更新",
        source="admin",
        actor=current_user,
        before_data={"marquee_notices": before_data},
        after_data={"marquee_notices": after_data},
    )
    await db.commit()
    return [_serialize_marquee_notice(row) for row in next_rows]


@router.patch("/users/{user_id}/note", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_customer_note(
    user_id: int,
    payload: UserNoteUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    user = await db.scalar(select(User).options(selectinload(User.profile)).where(User.id == user_id))
    if not user:
        raise not_found("user not found")
    if not user.profile:
        user.profile = CustomerProfile(user_id=user.id)
        db.add(user.profile)
        await db.flush()
    before_note = user.profile.note
    user.profile.note = payload.note.strip() if payload.note else None
    await write_business_event(
        db=db,
        entity_type="user",
        entity_id=user.id,
        entity_no=user.username,
        action_code="customer.note.updated",
        action_label="客户备注更新",
        source="admin",
        actor=current_user,
        before_data={"note": before_note},
        after_data={"note": user.profile.note},
    )
    await db.commit()
    return {"id": user.id, "note": user.profile.note}


@router.post("/wholesale-applications/{application_id}/review", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def review_wholesale_application(
    application_id: int,
    payload: WholesaleApplicationReviewIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.get(WholesaleApplication, application_id)
    if not row:
        raise not_found("wholesale application not found")
    user = await db.get(User, row.user_id)
    if not user:
        raise not_found("user not found")
    profile = await db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
    if not profile:
        profile = CustomerProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

    row.status = payload.status
    row.review_note = payload.review_note
    row.reviewed_by = current_user.id
    row.reviewed_at = datetime.now(UTC)
    before_role = user.role
    if payload.status == WholesaleApplicationStatus.APPROVED:
        user.role = UserRole.WHOLESALE
        profile.is_verified_wholesale = True
        profile.company_name = row.company_name or profile.company_name
        profile.store_name = row.store_name or profile.store_name
        profile.contact_name = row.contact_name or profile.contact_name
        if not profile.phone:
            profile.phone = row.contact_phone or profile.phone
        profile.business_license_url = row.business_license_url or profile.business_license_url
    elif payload.status == WholesaleApplicationStatus.REJECTED:
        profile.is_verified_wholesale = False
    await write_business_event(
        db=db,
        entity_type="wholesale_application",
        entity_id=row.id,
        entity_no=str(row.id),
        action_code="wholesale_application.reviewed",
        action_label="批发申请审核",
        source="admin",
        actor=current_user,
        before_data={"status": WholesaleApplicationStatus.PENDING.value, "role": before_role.value},
        after_data={
            "status": row.status.value,
            "role": user.role.value,
            "is_verified_wholesale": bool(profile.is_verified_wholesale),
        },
        note=row.review_note,
    )
    await create_customer_notification(
        db,
        user_id=user.id,
        title="申请结果通知",
        summary=(
            f"申请 #{row.id} 已通过审核，当前账号已切换为批发客户。"
            if payload.status == WholesaleApplicationStatus.APPROVED
            else f"申请 #{row.id} 未通过审核，请查看审核备注。"
        ),
        kind="wholesale",
        route="/pages/my/my",
        push_event_key="wholesale_reviewed",
        push_payload={
            "result": "已通过" if payload.status == WholesaleApplicationStatus.APPROVED else "已驳回",
            "merchant_name": row.company_name or row.store_name or user.username,
            "phone": row.contact_phone or profile.phone or "",
            "apply_time": row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
            "review_time": row.reviewed_at.isoformat() if row.reviewed_at else datetime.now(UTC).isoformat(),
            "status": "已通过" if payload.status == WholesaleApplicationStatus.APPROVED else "已驳回",
            "note": row.review_note or "请查看审核备注。",
        },
    )
    await db.commit()
    return {"id": row.id, "status": row.status.value}


@router.delete("/orders/{order_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_admin_order(
    order_id: int,
    payload: DeleteConfirmationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.confirmation_text.strip() != "确认删除此订单":
        raise bad_request("confirmation text does not match")
    order = await db.get(Order, order_id)
    if not order or order.deleted_at:
        raise not_found("order not found")
    await delete_order(db=db, order=order, operator=current_user, note="admin deleted order")
    await db.commit()
    return {"id": order.id, "order_no": order.order_no, "deleted": True}


@router.patch("/orders/{order_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def adjust_order(
    order_id: int,
    payload: OrderAdjustmentIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order or order.deleted_at:
        raise not_found("order not found")
    if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.DELETED}:
        raise bad_request("completed or terminated orders cannot be adjusted")

    fields = payload.model_fields_set
    if not fields:
        raise bad_request("at least one field is required")
    operational_fields = {"shipping_recipient", "shipping_phone", "shipping_address", "customer_note"}
    if fields & operational_fields and not (payload.reason or "").strip():
        raise bad_request("reason is required when changing customer information")

    before = {
        "shipping_recipient": order.shipping_recipient,
        "shipping_phone": order.shipping_phone,
        "shipping_address": order.shipping_address,
        "customer_note": order.customer_note or order.note,
        "internal_note": order.internal_note,
    }
    for field in ("shipping_recipient", "shipping_phone", "shipping_address", "customer_note", "internal_note"):
        if field in fields:
            value = getattr(payload, field)
            setattr(order, field, value.strip() if isinstance(value, str) and value.strip() else value)
    if "customer_note" in fields:
        order.note = order.customer_note
    after = {
        "shipping_recipient": order.shipping_recipient,
        "shipping_phone": order.shipping_phone,
        "shipping_address": order.shipping_address,
        "customer_note": order.customer_note,
        "internal_note": order.internal_note,
    }
    await write_business_event(
        db=db, entity_type="order", entity_id=order.id, entity_no=order.order_no,
        action_code="order.adjusted", action_label="订单信息调整", source="admin", actor=current_user,
        before_data=before, after_data=after, note=(payload.reason or "").strip() or None,
    )
    await db.commit()
    return {"id": order.id, "status": order.status.value, **after}


@router.post("/orders/{order_id}/terminate", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def terminate_admin_order(
    order_id: int,
    payload: OrderTerminationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order or order.deleted_at:
        raise not_found("order not found")
    await terminate_order(
        db=db, order=order, operator=current_user, reason=payload.reason,
        disposition=payload.disposition, internal_note=payload.internal_note,
    )
    await db.commit()
    return {"id": order.id, "status": order.status.value, "terminated_at": order.terminated_at.isoformat()}


@router.delete("/aftersales/{aftersale_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_admin_aftersale(
    aftersale_id: int,
    payload: DeleteConfirmationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.confirmation_text.strip() != "确认删除此售后":
        raise bad_request("confirmation text does not match")
    row = await db.get(AfterSaleRequest, aftersale_id)
    if not row or row.deleted_at:
        raise not_found("aftersale not found")
    row.deleted_at = datetime.now(UTC)
    row.deleted_by_user_id = current_user.id
    await write_business_event(
        db=db, entity_type="aftersale", entity_id=row.id, entity_no=f"AS{row.id}",
        action_code="aftersale.deleted", action_label="删除售后记录", source="admin", actor=current_user,
        before_data={
            "order_id": row.order_id,
            "status": row.status.value,
            "reason": row.reason.value,
            "process_type": row.process_type.value if row.process_type else None,
        },
        after_data={"deleted_at": row.deleted_at.isoformat()},
    )
    await db.commit()
    return {"id": row.id, "deleted": True}


@router.patch("/aftersales/{aftersale_id}/notes", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_aftersale_notes(
    aftersale_id: int,
    payload: AftersaleNotesIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = await db.get(AfterSaleRequest, aftersale_id)
    if not row or row.deleted_at:
        raise not_found("aftersale not found")
    fields = payload.model_fields_set
    if not fields:
        raise bad_request("at least one field is required")
    before = {"customer_note": row.customer_note or row.note, "internal_note": row.internal_note}
    if "customer_note" in fields:
        row.customer_note = (payload.customer_note or "").strip() or None
        row.note = row.customer_note
    if "internal_note" in fields:
        row.internal_note = (payload.internal_note or "").strip() or None
    after = {"customer_note": row.customer_note, "internal_note": row.internal_note}
    await write_business_event(
        db=db, entity_type="aftersale", entity_id=row.id, entity_no=f"AS{row.id}",
        action_code="aftersale.notes.updated", action_label="售后说明更新", source="admin", actor=current_user,
        before_data=before, after_data=after,
    )
    await db.commit()
    return {"id": row.id, **after}


@router.post("/ops/auto-cancel", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def run_auto_cancel(
    db: Annotated[AsyncSession, Depends(get_db)],
    cutoff_minutes: int = Query(default=10, ge=0, le=120),
) -> dict:
    canceled = await auto_cancel_expired_orders(db=db, cutoff_minutes=cutoff_minutes, batch_size=500)
    if canceled:
        await db.commit()
    return {"canceled": len(canceled), "order_nos": canceled}


@router.post("/ops/auto-complete-shipped", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def run_auto_complete_shipped(
    db: Annotated[AsyncSession, Depends(get_db)],
    express_days: int = Query(default=3, ge=0, le=30),
    offline_days: int = Query(default=10, ge=0, le=60),
) -> dict:
    completed = await auto_complete_shipped_orders(
        db=db,
        express_days=express_days,
        offline_days=offline_days,
        batch_size=500,
    )
    if completed:
        await db.commit()
    return {"completed": len(completed), "order_nos": completed}


@router.post("/orders/{order_id}/confirm-wechat-payment", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def confirm_wechat_payment(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    order = await db.get(Order, order_id)
    if not order:
        raise not_found("order not found")
    payment = await db.scalar(
        select(PaymentRecord)
        .where(PaymentRecord.order_id == order.id)
        .order_by(desc(PaymentRecord.id))
    )
    if not payment:
        payment = PaymentRecord(
            payment_no=f"PAY-MANUAL-{order.id}",
            order_id=order.id,
            channel="manual_admin",
            status=PaymentStatus.PAID,
            amount=order.payable_amount,
            provider_txn_no=f"MANUAL-{order.order_no}",
            provider_payload={"manual": True},
        )
        db.add(payment)
    else:
        payment.status = PaymentStatus.PAID
        payment.provider_txn_no = payment.provider_txn_no or f"MANUAL-{order.order_no}"
    await db.flush()
    await mark_order_paid(db=db, order=order, operator=current_user, source="admin", note="admin confirm wechat payment")
    await write_business_event(
        db=db,
        entity_type="payment",
        entity_id=payment.id,
        entity_no=payment.payment_no,
        action_code="payment.confirmed",
        action_label="确认微信收款",
        source="admin",
        actor=current_user,
        after_data={
            "status": payment.status.value,
            "amount": f"{payment.amount:.2f}",
            "provider_txn_no": payment.provider_txn_no,
            "channel": payment.channel,
        },
        note="admin confirm wechat payment",
    )
    await db.commit()
    return {"order_id": order.id, "order_no": order.order_no, "status": order.status.value}


@router.get("/print-jobs", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_print_jobs(db: Annotated[AsyncSession, Depends(get_db)]) -> list[dict]:
    rows = (await db.execute(
        select(PrintJob, Order, User)
        .join(Order, Order.id == PrintJob.order_id)
        .outerjoin(User, User.id == PrintJob.requested_by_user_id)
        .order_by(desc(PrintJob.id))
        .limit(300)
    )).all()
    return [{
        "id": job.id, "order_id": order.id, "order_no": order.order_no, "status": job.status,
        "document_type": job.document_type, "requested_by": user.username if user else "系统",
        "created_at": job.created_at.isoformat(), "payload": job.payload,
    } for job, order, user in rows]
