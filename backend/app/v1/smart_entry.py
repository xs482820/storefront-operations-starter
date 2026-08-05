from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.exceptions import bad_request
from app.db.session import get_db
from app.models.enums import StockChangeType, UserRole
from app.models.product import Inventory, Product, ProductSKU, SKUUnitConversion, Unit
from app.models.stock import StockLedger
from app.schemas.smart_entry import SmartEntryIn

router = APIRouter(prefix="/admin/smart-entry", tags=["smart-entry"])


@router.post("", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def smart_entry(
    payload: SmartEntryIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    created_products = 0
    updated_skus = 0

    for item in payload.items:
        product = await db.scalar(select(Product).where(Product.product_code == item.product_code))
        if not product:
            product = Product(
                name=item.product_name,
                brand=item.brand,
                product_code=item.product_code,
                description=item.spec,
                is_active=True,
            )
            db.add(product)
            await db.flush()
            created_products += 1

        sku = await db.scalar(select(ProductSKU).where(ProductSKU.sku_code == item.sku_code))
        if not sku:
            sku = ProductSKU(
                product_id=product.id,
                sku_code=item.sku_code,
                sku_name=item.sku_name,
                attrs={"spec": item.spec} if item.spec else {},
                retail_price=0,
                wholesale_price=0,
                min_wholesale_base_qty=1,
                is_active=True,
            )
            db.add(sku)
            await db.flush()

            piece_unit = await db.scalar(select(Unit).where(Unit.code == "piece"))
            if not piece_unit:
                piece_unit = Unit(code="piece", name="件", level=1)
                db.add(piece_unit)
                await db.flush()

            db.add(
                SKUUnitConversion(
                    sku_id=sku.id,
                    unit_id=piece_unit.id,
                    to_base_factor=1,
                    is_base_unit=True,
                )
            )
            db.add(Inventory(sku_id=sku.id, on_hand_base_qty=0, reserved_base_qty=0, version=0))

        inventory = await db.scalar(select(Inventory).where(Inventory.sku_id == sku.id).with_for_update())
        if not inventory:
            raise bad_request(f"inventory missing for sku {sku.sku_code}")

        inventory.on_hand_base_qty += item.quantity_base
        inventory.version += 1
        db.add(
            StockLedger(
                sku_id=sku.id,
                delta_base_qty=item.quantity_base,
                change_type=StockChangeType.INBOUND,
                note=f"smart-entry:{payload.source}",
            )
        )
        updated_skus += 1

    await db.commit()
    return {
        "source": payload.source,
        "created_products": created_products,
        "updated_skus": updated_skus,
    }
