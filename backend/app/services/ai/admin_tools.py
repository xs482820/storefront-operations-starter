from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.aftersale import AfterSaleRequest
from app.models.enums import AfterSaleStatus, OrderStatus, UserRole, WholesaleApplicationStatus
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductSKU
from app.models.user import User, WholesaleApplication
from app.schemas.admin_ai import AdminAiPageContext, AdminAiToolResult


def _amount(value: Decimal | int | float | None) -> str:
    return f"{Decimal(value or 0):.2f}"


def _user_name(user: User | None) -> str:
    if not user:
        return "unknown"
    if user.profile and user.profile.display_name:
        return user.profile.display_name
    return user.username


def _tool(name: str, title: str, summary: str, data: dict[str, Any]) -> AdminAiToolResult:
    return AdminAiToolResult(name=name, title=title, summary=summary, data=data)


async def collect_admin_ai_tools(
    db: AsyncSession,
    page_context: AdminAiPageContext | None,
) -> list[AdminAiToolResult]:
    now = datetime.now(UTC)
    today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    today_end = datetime.combine(now.date(), time.max, tzinfo=UTC)
    week_start = today_start - timedelta(days=6)

    today_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.payable_amount), 0)).where(
            Order.paid_at.is_not(None),
            Order.paid_at >= today_start,
            Order.paid_at <= today_end,
        )
    )
    paid_order_count = await db.scalar(
        select(func.count(Order.id)).where(
            Order.paid_at.is_not(None),
            Order.paid_at >= today_start,
            Order.paid_at <= today_end,
        )
    ) or 0
    pending_payment_count = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING_PAYMENT)
    ) or 0
    awaiting_shipment_count = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.AWAITING_SHIPMENT)
    ) or 0
    shipped_count = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.SHIPPED)
    ) or 0
    pending_aftersale_count = await db.scalar(
        select(func.count(AfterSaleRequest.id)).where(AfterSaleRequest.status == AfterSaleStatus.PENDING)
    ) or 0
    pending_wholesale_count = await db.scalar(
        select(func.count(WholesaleApplication.id)).where(
            WholesaleApplication.status == WholesaleApplicationStatus.PENDING
        )
    ) or 0
    low_stock_sku_count = await db.scalar(
        select(func.count(ProductSKU.id)).where(ProductSKU.is_active.is_(True), ProductSKU.online_stock <= 10)
    ) or 0
    active_product_count = await db.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True))
    ) or 0

    dashboard_tool = _tool(
        "dashboard_snapshot",
        "经营快照",
        (
            f"今日营收 ¥{_amount(today_revenue)}，已付款订单 {int(paid_order_count)}；"
            f"待付款 {int(pending_payment_count)}、待发货 {int(awaiting_shipment_count)}、待售后 {int(pending_aftersale_count)}。"
        ),
        {
            "today_revenue": _amount(today_revenue),
            "today_paid_orders": int(paid_order_count),
            "pending_payment_orders": int(pending_payment_count),
            "awaiting_shipment_orders": int(awaiting_shipment_count),
            "shipped_orders": int(shipped_count),
            "pending_aftersales": int(pending_aftersale_count),
            "pending_wholesale_applications": int(pending_wholesale_count),
            "active_products": int(active_product_count),
            "low_stock_skus": int(low_stock_sku_count),
        },
    )

    recent_orders = (
        await db.scalars(
            select(Order)
            .where(Order.status.in_([OrderStatus.PENDING_PAYMENT, OrderStatus.AWAITING_SHIPMENT, OrderStatus.SHIPPED]))
            .order_by(desc(Order.id))
            .limit(8)
        )
    ).all()
    recent_order_ids = [row.id for row in recent_orders]
    customer_ids = [row.customer_id for row in recent_orders if row.customer_id]
    users = (
        await db.scalars(select(User).options(selectinload(User.profile)).where(User.id.in_(customer_ids)))
    ).all() if customer_ids else []
    user_map = {user.id: user for user in users}
    order_items = (
        await db.scalars(select(OrderItem).where(OrderItem.order_id.in_(recent_order_ids)).order_by(OrderItem.id.asc()))
    ).all() if recent_order_ids else []
    first_item_by_order: dict[int, OrderItem] = {}
    for item in order_items:
        first_item_by_order.setdefault(item.order_id, item)
    order_rows = [
        {
            "order_no": row.order_no,
            "status": row.status.value,
            "customer": _user_name(user_map.get(row.customer_id)) if row.customer_id else "unknown",
            "amount": _amount(row.payable_amount),
            "shipping_mode": row.shipping_mode.value if row.shipping_mode else None,
            "item": first_item_by_order.get(row.id).product_name_snapshot if first_item_by_order.get(row.id) else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in recent_orders
    ]

    low_stock_rows = (
        await db.scalars(
            select(ProductSKU)
            .options(selectinload(ProductSKU.product))
            .where(ProductSKU.is_active.is_(True), ProductSKU.online_stock <= 10)
            .order_by(ProductSKU.online_stock.asc(), desc(ProductSKU.id))
            .limit(10)
        )
    ).all()
    low_stock_items = [
        {
            "sku_id": row.id,
            "sku_code": row.sku_code,
            "product_name": row.product.name if row.product else "",
            "spec": " / ".join([item for item in [row.spec_value_1, row.spec_value_2] if item]) or row.sku_label,
            "stock": row.online_stock,
        }
        for row in low_stock_rows
    ]

    pending_aftersales = (
        await db.scalars(
            select(AfterSaleRequest)
            .where(AfterSaleRequest.status == AfterSaleStatus.PENDING)
            .order_by(desc(AfterSaleRequest.id))
            .limit(8)
        )
    ).all()
    aftersale_order_ids = [row.order_id for row in pending_aftersales]
    orders = (
        await db.scalars(select(Order).where(Order.id.in_(aftersale_order_ids)))
    ).all() if aftersale_order_ids else []
    order_map = {row.id: row for row in orders}
    aftersale_items = [
        {
            "id": row.id,
            "order_no": order_map[row.order_id].order_no if order_map.get(row.order_id) else None,
            "reason": row.reason.value,
            "refund_amount": _amount(row.refund_amount),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in pending_aftersales
    ]

    pending_applications = (
        await db.scalars(
            select(WholesaleApplication)
            .where(WholesaleApplication.status == WholesaleApplicationStatus.PENDING)
            .order_by(desc(WholesaleApplication.id))
            .limit(8)
        )
    ).all()
    wholesale_items = [
        {
            "id": row.id,
            "store_name": row.store_name,
            "company_name": row.company_name,
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in pending_applications
    ]

    weekly_order_count = await db.scalar(
        select(func.count(Order.id)).where(Order.created_at >= week_start, Order.created_at <= today_end)
    ) or 0
    weekly_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.payable_amount), 0)).where(
            Order.paid_at.is_not(None),
            Order.paid_at >= week_start,
            Order.paid_at <= today_end,
        )
    )

    return [
        dashboard_tool,
        _tool(
            "recent_orders",
            "近期订单",
            f"最近待处理订单 {len(order_rows)} 条，本周订单 {int(weekly_order_count)}，本周营收 ¥{_amount(weekly_revenue)}。",
            {"items": order_rows, "weekly_orders": int(weekly_order_count), "weekly_revenue": _amount(weekly_revenue)},
        ),
        _tool(
            "low_stock",
            "低库存",
            f"当前低库存 SKU {int(low_stock_sku_count)} 个，优先关注库存最低的 {len(low_stock_items)} 个。",
            {"items": low_stock_items, "total": int(low_stock_sku_count)},
        ),
        _tool(
            "pending_aftersales",
            "待处理售后",
            f"待处理售后 {int(pending_aftersale_count)} 单。",
            {"items": aftersale_items, "total": int(pending_aftersale_count)},
        ),
        _tool(
            "pending_wholesale",
            "待认证审核",
            f"待认证审核 {int(pending_wholesale_count)} 个。",
            {"items": wholesale_items, "total": int(pending_wholesale_count)},
        ),
        _tool(
            "page_context",
            "当前位置",
            f"管理员当前在 {page_context.route if page_context else '未知页面'}。",
            {"page_context": page_context.model_dump() if page_context else None},
        ),
    ]
