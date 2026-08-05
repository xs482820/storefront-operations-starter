import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.exceptions import bad_request
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.models.order import Order
from app.models.payment import PaymentRecord
from app.models.stock import StockDocument
from app.models.user import User
from app.schemas.report import SalesRoleBreakdownOut, SalesSummaryOut

router = APIRouter(prefix="/reports", tags=["reports"])


def _date_range(from_date: date | None, to_date: date | None, default_days: int = 7) -> tuple[datetime, datetime, date, date]:
    today = datetime.now(UTC).date()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = to_date - timedelta(days=default_days - 1)
    if from_date > to_date:
        raise bad_request("from_date cannot be greater than to_date")
    return (
        datetime.combine(from_date, time.min, tzinfo=UTC),
        datetime.combine(to_date, time.max, tzinfo=UTC),
        from_date,
        to_date,
    )


def _csv_response(filename: str, rows: list[list[str]]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sales-summary", response_model=SalesSummaryOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def sales_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> SalesSummaryOut:
    from_dt, to_dt, start, end = _date_range(from_date, to_date, default_days=7)
    paid_like = [OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED, OrderStatus.COMPLETED]
    paid_case = case((Order.status.in_(paid_like), 1), else_=0)
    paid_amount_case = case((Order.status.in_(paid_like), Order.payable_amount), else_=Decimal("0.00"))
    canceled_case = case((Order.status == OrderStatus.CANCELED, 1), else_=0)

    total_row = (
        await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(paid_case), 0),
                func.coalesce(func.sum(canceled_case), 0),
                func.coalesce(func.sum(paid_amount_case), 0),
            ).where(Order.created_at >= from_dt, Order.created_at <= to_dt)
        )
    ).one()

    role_rows = (
        await db.execute(
            select(
                User.role,
                func.count(Order.id),
                func.coalesce(func.sum(paid_case), 0),
                func.coalesce(func.sum(paid_amount_case), 0),
            )
            .join(User, User.id == Order.customer_id, isouter=True)
            .where(Order.created_at >= from_dt, Order.created_at <= to_dt)
            .group_by(User.role)
            .order_by(User.role.asc())
        )
    ).all()
    by_role = [
        SalesRoleBreakdownOut(
            role=(row[0].value if row[0] else "unknown"),
            orders=int(row[1] or 0),
            paid_orders=int(row[2] or 0),
            paid_amount=Decimal(row[3] or 0),
        )
        for row in role_rows
    ]
    return SalesSummaryOut(
        from_date=start.isoformat(),
        to_date=end.isoformat(),
        total_orders=int(total_row[0] or 0),
        paid_orders=int(total_row[1] or 0),
        canceled_orders=int(total_row[2] or 0),
        paid_amount=Decimal(total_row[3] or 0),
        by_role=by_role,
    )


@router.get("/exports/orders.csv", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def export_orders_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> StreamingResponse:
    from_dt, to_dt, start, end = _date_range(from_date, to_date, default_days=7)
    rows = (
        await db.execute(
            select(
                Order.order_no,
                Order.status,
                Order.customer_id,
                Order.total_amount,
                Order.discount_amount,
                Order.shipping_fee,
                Order.payable_amount,
                Order.shipping_policy,
                Order.created_at,
            )
            .where(Order.created_at >= from_dt, Order.created_at <= to_dt)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    ).all()
    csv_rows: list[list[str]] = [[
        "order_no", "status", "customer_id", "total_amount", "discount_amount",
        "shipping_fee", "payable_amount", "shipping_policy", "created_at",
    ]]
    for row in rows:
        csv_rows.append([
            str(row[0]),
            row[1].value,
            str(row[2] or ""),
            f"{Decimal(row[3]):.2f}",
            f"{Decimal(row[4]):.2f}",
            f"{Decimal(row[5]):.2f}",
            f"{Decimal(row[6]):.2f}",
            str(row[7] or ""),
            row[8].isoformat() if row[8] else "",
        ])
    filename = f"orders_{start.isoformat()}_{end.isoformat()}.csv"
    return _csv_response(filename, csv_rows)


@router.get("/exports/payments.csv", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def export_payments_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> StreamingResponse:
    from_dt, to_dt, start, end = _date_range(from_date, to_date, default_days=7)
    rows = (
        await db.execute(
            select(
                PaymentRecord.payment_no,
                Order.order_no,
                PaymentRecord.channel,
                PaymentRecord.status,
                PaymentRecord.amount,
                PaymentRecord.provider_txn_no,
                PaymentRecord.created_at,
            )
            .join(Order, Order.id == PaymentRecord.order_id)
            .where(PaymentRecord.created_at >= from_dt, PaymentRecord.created_at <= to_dt)
            .order_by(PaymentRecord.created_at.desc())
            .limit(limit)
        )
    ).all()
    csv_rows: list[list[str]] = [[
        "payment_no", "order_no", "channel", "status", "amount", "provider_txn_no", "created_at",
    ]]
    for row in rows:
        csv_rows.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            row[3].value,
            f"{Decimal(row[4]):.2f}",
            str(row[5] or ""),
            row[6].isoformat() if row[6] else "",
        ])
    filename = f"payments_{start.isoformat()}_{end.isoformat()}.csv"
    return _csv_response(filename, csv_rows)


@router.get("/exports/stock-documents.csv", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def export_stock_documents_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> StreamingResponse:
    from_dt, to_dt, start, end = _date_range(from_date, to_date, default_days=7)
    rows = (
        await db.execute(
            select(
                StockDocument.doc_no,
                StockDocument.doc_type,
                StockDocument.source,
                StockDocument.total_items,
                StockDocument.total_base_qty,
                StockDocument.note,
                StockDocument.created_at,
            )
            .where(StockDocument.created_at >= from_dt, StockDocument.created_at <= to_dt)
            .order_by(StockDocument.created_at.desc())
            .limit(limit)
        )
    ).all()
    csv_rows: list[list[str]] = [[
        "doc_no", "doc_type", "source", "total_items", "total_base_qty", "note", "created_at",
    ]]
    for row in rows:
        csv_rows.append([
            str(row[0]),
            row[1].value if hasattr(row[1], "value") else str(row[1]),
            str(row[2] or ""),
            str(row[3] or 0),
            str(row[4] or 0),
            str(row[5] or ""),
            row[6].isoformat() if row[6] else "",
        ])
    filename = f"stock_documents_{start.isoformat()}_{end.isoformat()}.csv"
    return _csv_response(filename, csv_rows)
