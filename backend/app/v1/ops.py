from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.ops import (
    AutoCloseResultOut,
    LowStockItemOut,
    MaintenanceRunOut,
    PaymentAnomalyOut,
    PaymentTimeoutCompensateOut,
    PaymentReconcileResultOut,
)
from app.services.ops_jobs import (
    close_expired_pending_orders,
    compensate_timeout_payments,
    reconcile_paid_pending_orders,
    scan_low_stock_items,
    scan_payment_anomalies,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.post(
    "/jobs/auto-close-expired",
    response_model=AutoCloseResultOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_auto_close_expired(
    db: Annotated[AsyncSession, Depends(get_db)],
    cutoff_minutes: int = Query(default=30, ge=1, le=24 * 60),
    batch_size: int = Query(default=200, ge=1, le=1000),
) -> AutoCloseResultOut:
    scanned, closed_order_nos = await close_expired_pending_orders(
        db=db,
        cutoff_minutes=cutoff_minutes,
        batch_size=batch_size,
    )
    if closed_order_nos:
        await db.commit()
    return AutoCloseResultOut(
        cutoff_minutes=cutoff_minutes,
        scanned=scanned,
        closed=len(closed_order_nos),
        closed_order_nos=closed_order_nos,
    )


@router.get(
    "/jobs/low-stock",
    response_model=list[LowStockItemOut],
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_low_stock_scan(
    db: Annotated[AsyncSession, Depends(get_db)],
    threshold: int = Query(default=10, ge=0, le=1000000),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[LowStockItemOut]:
    rows = await scan_low_stock_items(db=db, threshold=threshold, limit=limit)
    return [LowStockItemOut(**row) for row in rows]


@router.get(
    "/jobs/payment-anomalies",
    response_model=list[PaymentAnomalyOut],
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_payment_anomaly_scan(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=300, ge=50, le=2000),
) -> list[PaymentAnomalyOut]:
    rows = await scan_payment_anomalies(db=db, limit=limit)
    return [PaymentAnomalyOut(**row) for row in rows]


@router.post(
    "/jobs/daily-maintenance",
    response_model=MaintenanceRunOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_daily_maintenance(
    db: Annotated[AsyncSession, Depends(get_db)],
    close_cutoff_minutes: int = Query(default=30, ge=1, le=24 * 60),
    low_stock_threshold: int = Query(default=10, ge=0, le=1000000),
) -> MaintenanceRunOut:
    scanned, closed_order_nos = await close_expired_pending_orders(
        db=db,
        cutoff_minutes=close_cutoff_minutes,
        batch_size=1000,
    )
    low_stock_rows = await scan_low_stock_items(db=db, threshold=low_stock_threshold, limit=500)
    anomalies = await scan_payment_anomalies(db=db, limit=800)
    if closed_order_nos:
        await db.commit()
    return MaintenanceRunOut(
        auto_close=AutoCloseResultOut(
            cutoff_minutes=close_cutoff_minutes,
            scanned=scanned,
            closed=len(closed_order_nos),
            closed_order_nos=closed_order_nos,
        ),
        low_stock_count=len(low_stock_rows),
        payment_anomaly_count=len(anomalies),
    )


@router.post(
    "/jobs/payment-reconcile",
    response_model=PaymentReconcileResultOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_payment_reconcile(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=500, ge=50, le=5000),
) -> PaymentReconcileResultOut:
    scanned, fixed_order_nos = await reconcile_paid_pending_orders(db=db, limit=limit)
    if fixed_order_nos:
        await db.commit()
    return PaymentReconcileResultOut(
        scanned=scanned,
        fixed=len(fixed_order_nos),
        fixed_order_nos=fixed_order_nos,
    )


@router.post(
    "/jobs/payment-timeout-compensate",
    response_model=PaymentTimeoutCompensateOut,
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def run_payment_timeout_compensate(
    db: Annotated[AsyncSession, Depends(get_db)],
    cutoff_minutes: int = Query(default=30, ge=1, le=24 * 60),
    batch_size: int = Query(default=500, ge=1, le=5000),
) -> PaymentTimeoutCompensateOut:
    scanned, canceled_order_nos, failed_payments, repaired_orders = await compensate_timeout_payments(
        db=db,
        cutoff_minutes=cutoff_minutes,
        batch_size=batch_size,
    )
    if canceled_order_nos or failed_payments or repaired_orders:
        await db.commit()
    return PaymentTimeoutCompensateOut(
        cutoff_minutes=cutoff_minutes,
        scanned_orders=scanned,
        canceled_orders=len(canceled_order_nos),
        failed_payments=failed_payments,
        repaired_orders=repaired_orders,
        canceled_order_nos=canceled_order_nos,
    )
