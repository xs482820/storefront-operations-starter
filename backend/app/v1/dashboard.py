from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.models.order import Order
from app.models.payment import PaymentRecord
from app.models.product import Inventory, Product, ProductSKU
from app.models.aftersale import AfterSaleRequest
from app.models.stock import StockDocument
from app.models.user import User
from app.schemas.dashboard import DashboardSalesOverviewOut, DashboardSalesPointOut, DashboardSummaryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardSummaryOut:
    total_products = await db.scalar(select(func.count(Product.id))) or 0
    total_skus = await db.scalar(select(func.count(ProductSKU.id))) or 0
    total_users = await db.scalar(select(func.count(User.id))) or 0
    total_orders = await db.scalar(select(func.count(Order.id))) or 0
    total_stock_documents = await db.scalar(select(func.count(StockDocument.id))) or 0
    total_payments = await db.scalar(select(func.count(PaymentRecord.id))) or 0
    total_aftersales = await db.scalar(select(func.count(AfterSaleRequest.id))) or 0
    pending_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING_PAYMENT)
    ) or 0
    paid_orders = await db.scalar(
        select(func.count(Order.id)).where(Order.status.in_([OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED]))
    ) or 0
    low_stock_skus = await db.scalar(
        select(func.count(Inventory.id)).where(Inventory.on_hand_base_qty <= 10)
    ) or 0
    total_inventory_base_qty = await db.scalar(select(func.coalesce(func.sum(Inventory.on_hand_base_qty), 0))) or 0
    inventory_value_stmt = (
        select(func.coalesce(func.sum(Inventory.on_hand_base_qty * ProductSKU.wholesale_price), 0))
        .join(ProductSKU, ProductSKU.id == Inventory.sku_id)
    )
    total_inventory_value = await db.scalar(inventory_value_stmt) or Decimal("0.00")

    return DashboardSummaryOut(
        total_products=total_products,
        total_skus=total_skus,
        total_users=total_users,
        total_orders=total_orders,
        total_stock_documents=total_stock_documents,
        total_payments=total_payments,
        total_aftersales=total_aftersales,
        pending_orders=pending_orders,
        paid_orders=paid_orders,
        low_stock_skus=low_stock_skus,
        total_inventory_base_qty=total_inventory_base_qty,
        total_inventory_value=Decimal(total_inventory_value),
    )


@router.get("/sales-overview", response_model=DashboardSalesOverviewOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def dashboard_sales_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=90),
) -> DashboardSalesOverviewOut:
    today = datetime.now(UTC).date()
    from_date = today - timedelta(days=days - 1)
    from_dt = datetime.combine(from_date, time.min, tzinfo=UTC)
    to_dt = datetime.combine(today, time.max, tzinfo=UTC)

    paid_case = case((Order.status.in_([OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED, OrderStatus.COMPLETED]), 1), else_=0)
    paid_amount_case = case(
        (Order.status.in_([OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED, OrderStatus.COMPLETED]), Order.payable_amount),
        else_=Decimal("0.00"),
    )
    canceled_case = case((Order.status == OrderStatus.CANCELED, 1), else_=0)

    total_row = (
        await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(paid_case), 0),
                func.coalesce(func.sum(paid_amount_case), 0),
                func.coalesce(func.sum(canceled_case), 0),
            ).where(Order.created_at >= from_dt, Order.created_at <= to_dt)
        )
    ).one()

    date_bucket = func.date(Order.created_at)
    rows = (
        await db.execute(
            select(
                date_bucket.label("day"),
                func.count(Order.id),
                func.coalesce(func.sum(paid_case), 0),
                func.coalesce(func.sum(paid_amount_case), 0),
            )
            .where(Order.created_at >= from_dt, Order.created_at <= to_dt)
            .group_by(date_bucket)
            .order_by(date_bucket.asc())
        )
    ).all()
    by_day: dict[date, tuple[int, int, Decimal]] = {}
    for row in rows:
        by_day[row[0]] = (int(row[1]), int(row[2]), Decimal(row[3]))

    points: list[DashboardSalesPointOut] = []
    for i in range(days):
        d = from_date + timedelta(days=i)
        orders, paid_orders, paid_amount = by_day.get(d, (0, 0, Decimal("0.00")))
        points.append(
            DashboardSalesPointOut(
                date=d.isoformat(),
                orders=orders,
                paid_orders=paid_orders,
                paid_amount=paid_amount,
            )
        )

    return DashboardSalesOverviewOut(
        from_date=from_date.isoformat(),
        to_date=today.isoformat(),
        total_orders=int(total_row[0] or 0),
        total_paid_orders=int(total_row[1] or 0),
        total_paid_amount=Decimal(total_row[2] or 0),
        total_canceled_orders=int(total_row[3] or 0),
        points=points,
    )
