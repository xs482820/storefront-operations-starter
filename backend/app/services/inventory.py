from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import bad_request, not_found
from app.models.enums import StockChangeReason
from app.models.product import OnlineStockLog, ProductSKU
from app.models.user import User


async def lock_sku(db: AsyncSession, sku_id: int) -> ProductSKU:
    sku = await db.scalar(select(ProductSKU).where(ProductSKU.id == sku_id).with_for_update())
    if not sku:
        raise not_found("sku not found")
    return sku


async def change_online_stock(
    db: AsyncSession,
    sku_id: int,
    delta_qty: int,
    reason: StockChangeReason,
    operator: User | None = None,
    note: str | None = None,
    ref_order_no: str | None = None,
) -> ProductSKU:
    sku = await lock_sku(db, sku_id)
    before_qty = sku.online_stock
    after_qty = before_qty + delta_qty
    if after_qty < 0:
        raise bad_request("online stock is insufficient")

    sku.online_stock = after_qty
    db.add(
        OnlineStockLog(
            sku_id=sku.id,
            delta_qty=delta_qty,
            before_qty=before_qty,
            after_qty=after_qty,
            reason=reason,
            ref_order_no=ref_order_no,
            operator_user_id=operator.id if operator else None,
            note=note,
        )
    )
    await db.flush()
    return sku


async def set_online_stock(
    db: AsyncSession,
    sku_id: int,
    target_qty: int,
    operator: User | None = None,
    note: str | None = None,
) -> ProductSKU:
    if target_qty < 0:
        raise bad_request("target_qty cannot be negative")
    sku = await lock_sku(db, sku_id)
    before_qty = sku.online_stock
    sku.online_stock = target_qty
    db.add(
        OnlineStockLog(
            sku_id=sku.id,
            delta_qty=target_qty - before_qty,
            before_qty=before_qty,
            after_qty=target_qty,
            reason=StockChangeReason.ADMIN_SET,
            operator_user_id=operator.id if operator else None,
            note=note,
        )
    )
    await db.flush()
    return sku
