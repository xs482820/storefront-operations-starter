from typing import Annotated

from fastapi import APIRouter, Depends, Query
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles, wholesale_price_limit
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.product import Inventory, Product, ProductCategory, ProductSKU, SKUUnitConversion, Unit
from app.models.user import User
from app.schemas.product import (
    InventoryAdjustIn,
    ProductCategoryCreateIn,
    ProductCategoryOut,
    ProductCategoryUpdateIn,
    ProductOptionOut,
    ProductQuickCreateIn,
    ProductQuickCreateOut,
    ProductDetailOut,
    ProductStatusUpdateIn,
    ProductUpdateIn,
    PriceViewOut,
    ProductCreateIn,
    ProductListOut,
    StockDeductIn,
    UnitConversionOut,
)
from app.services.inventory import adjust_inventory, deduct_by_unit

router = APIRouter(prefix="/products", tags=["products"])


def _slugify_category_code(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "category"


def _serialize_category(item: ProductCategory, children_map: dict[int, list[ProductCategory]]) -> ProductCategoryOut:
    return ProductCategoryOut(
        id=item.id,
        name=item.name,
        code=item.code,
        parent_id=item.parent_id,
        sort_order=item.sort_order,
        is_active=item.is_active,
        children=[_serialize_category(child, children_map) for child in children_map.get(item.id, [])],
    )


async def _load_categories_tree(db: AsyncSession, include_inactive: bool = False) -> list[ProductCategoryOut]:
    stmt = select(ProductCategory).order_by(ProductCategory.sort_order.asc(), ProductCategory.id.asc())
    if not include_inactive:
        stmt = stmt.where(ProductCategory.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    children_map: dict[int, list[ProductCategory]] = {}
    roots: list[ProductCategory] = []
    for item in rows:
        if item.parent_id:
            children_map.setdefault(item.parent_id, []).append(item)
        else:
            roots.append(item)
    return [_serialize_category(item, children_map) for item in roots]


async def _validate_product_categories(
    db: AsyncSession,
    category_name: str | None,
    subcategory_name: str | None,
) -> tuple[str | None, str | None]:
    category = category_name.strip() if category_name else None
    subcategory = subcategory_name.strip() if subcategory_name else None
    if subcategory and not category:
        raise bad_request("subcategory requires category")
    if category:
        category_row = await db.scalar(
            select(ProductCategory).where(
                ProductCategory.name == category,
                ProductCategory.parent_id.is_(None),
                ProductCategory.is_active.is_(True),
            )
        )
        if not category_row:
            raise bad_request("category does not exist or is inactive")
        if subcategory:
            sub_row = await db.scalar(
                select(ProductCategory).where(
                    ProductCategory.name == subcategory,
                    ProductCategory.parent_id == category_row.id,
                    ProductCategory.is_active.is_(True),
                )
            )
            if not sub_row:
                raise bad_request("subcategory does not exist or is inactive")
    return category, subcategory


@router.post("", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_product(
    payload: ProductCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    product_exists = await db.scalar(select(Product.id).where(Product.product_code == payload.product_code))
    if product_exists:
        raise bad_request("product_code already exists")
    category, subcategory = await _validate_product_categories(db, payload.category, payload.subcategory)

    product = Product(
        name=payload.name,
        brand=payload.brand,
        category=category,
        subcategory=subcategory,
        product_code=payload.product_code,
        description=payload.description,
        is_active=True,
    )
    db.add(product)
    await db.flush()

    for sku_in in payload.skus:
        sku = ProductSKU(
            product_id=product.id,
            sku_code=sku_in.sku_code,
            sku_name=sku_in.sku_name,
            attrs=sku_in.attrs,
            retail_price=sku_in.retail_price,
            wholesale_price=sku_in.wholesale_price,
            min_wholesale_base_qty=sku_in.min_wholesale_base_qty,
            is_active=True,
        )
        db.add(sku)
        await db.flush()

        base_units = [c for c in sku_in.conversions if c.is_base_unit]
        if len(base_units) != 1:
            raise bad_request("exactly one base unit is required in each SKU conversion list")

        for conv_in in sku_in.conversions:
            unit = await db.scalar(select(Unit).where(Unit.code == conv_in.unit_code))
            if not unit:
                unit = Unit(code=conv_in.unit_code, name=conv_in.unit_name, level=conv_in.unit_level)
                db.add(unit)
                await db.flush()

            db.add(
                SKUUnitConversion(
                    sku_id=sku.id,
                    unit_id=unit.id,
                    to_base_factor=conv_in.to_base_factor,
                    is_base_unit=conv_in.is_base_unit,
                )
            )

        db.add(Inventory(sku_id=sku.id, on_hand_base_qty=0, reserved_base_qty=0, version=0))

    await db.commit()
    return {"id": product.id, "product_code": product.product_code, "message": "created"}


@router.post("/quick-create", response_model=ProductQuickCreateOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def quick_create_product(
    payload: ProductQuickCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductQuickCreateOut:
    product_exists = await db.scalar(select(Product.id).where(Product.product_code == payload.product_code))
    if product_exists:
        raise bad_request("product_code already exists")
    sku_exists = await db.scalar(select(ProductSKU.id).where(ProductSKU.sku_code == payload.sku_code))
    if sku_exists:
        raise bad_request("sku_code already exists")
    category, subcategory = await _validate_product_categories(db, payload.category, payload.subcategory)

    product = Product(
        name=payload.name,
        brand=payload.brand,
        category=category,
        subcategory=subcategory,
        product_code=payload.product_code,
        description=None,
        is_active=True,
    )
    db.add(product)
    await db.flush()

    sku = ProductSKU(
        product_id=product.id,
        sku_code=payload.sku_code,
        sku_name=payload.sku_name,
        attrs=payload.attrs,
        retail_price=payload.retail_price,
        wholesale_price=payload.wholesale_price,
        min_wholesale_base_qty=payload.min_wholesale_base_qty,
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

    if payload.box_to_piece_factor > 1:
        box_unit = await db.scalar(select(Unit).where(Unit.code == "box"))
        if not box_unit:
            box_unit = Unit(code="box", name="箱", level=3)
            db.add(box_unit)
            await db.flush()
        db.add(
            SKUUnitConversion(
                sku_id=sku.id,
                unit_id=box_unit.id,
                to_base_factor=payload.box_to_piece_factor,
                is_base_unit=False,
            )
        )

    db.add(Inventory(sku_id=sku.id, on_hand_base_qty=0, reserved_base_qty=0, version=0))
    await db.commit()
    return ProductQuickCreateOut(
        product_id=product.id,
        sku_id=sku.id,
        product_code=product.product_code,
        sku_code=sku.sku_code,
        message="quick created",
    )


@router.get("", response_model=list[ProductListOut])
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    _: Annotated[None, Depends(wholesale_price_limit)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
    category: str | None = Query(default=None, min_length=1, max_length=64),
    include_inactive: bool = Query(default=False),
) -> list[ProductListOut]:
    stmt = (
        select(Product, ProductSKU, Inventory)
        .join(ProductSKU, ProductSKU.product_id == Product.id)
        .join(Inventory, Inventory.sku_id == ProductSKU.id)
        .order_by(Product.id.desc(), ProductSKU.id.desc())
    )
    if not include_inactive or current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Product.is_active.is_(True), ProductSKU.is_active.is_(True))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            Product.name.ilike(like_kw)
            | ProductSKU.sku_name.ilike(like_kw)
            | ProductSKU.sku_code.ilike(like_kw)
        )
    if category:
        stmt = stmt.where(Product.category == category.strip())

    rows = (await db.execute(stmt)).all()

    sku_ids = sorted({sku.id for _, _, sku in rows})
    conversion_map: dict[int, list[UnitConversionOut]] = {}
    if sku_ids:
        conversion_rows = (
            await db.scalars(
                select(SKUUnitConversion)
                .where(SKUUnitConversion.sku_id.in_(sku_ids))
                .options(selectinload(SKUUnitConversion.unit))
            )
        ).all()
        for item in conversion_rows:
            if not item.unit:
                continue
            conversion_map.setdefault(item.sku_id, []).append(
                UnitConversionOut(
                    unit_code=item.unit.code,
                    unit_name=item.unit.name,
                    to_base_factor=item.to_base_factor,
                    is_base_unit=item.is_base_unit,
                )
            )
        for sid in conversion_map:
            conversion_map[sid] = sorted(
                conversion_map[sid],
                key=lambda x: (0 if x.is_base_unit else 1, x.to_base_factor, x.unit_code),
            )

    out: list[ProductListOut] = []
    for product, sku, inventory in rows:
        wholesale_price = sku.wholesale_price if current_user.role in {UserRole.ADMIN, UserRole.WHOLESALE} else None
        out.append(
            ProductListOut(
                product_id=product.id,
                product_code=product.product_code,
                sku_id=sku.id,
                product_name=product.name,
                category=product.category,
                subcategory=product.subcategory,
                sku_name=sku.sku_name,
                sku_code=sku.sku_code,
                attrs=sku.attrs,
                min_wholesale_base_qty=sku.min_wholesale_base_qty,
                product_is_active=product.is_active,
                sku_is_active=sku.is_active,
                price=PriceViewOut(
                    retail_price=sku.retail_price,
                    wholesale_price=wholesale_price,
                ),
                on_hand_base_qty=inventory.on_hand_base_qty,
                reserved_base_qty=inventory.reserved_base_qty,
                sellable_stock=inventory.on_hand_base_qty - inventory.reserved_base_qty,
                conversions=conversion_map.get(sku.id, []),
                description=product.description,
            )
        )
    return out


@router.get("/{sku_id}", response_model=ProductDetailOut)
async def get_product_detail(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductDetailOut:
    row = await db.execute(
        select(Product, ProductSKU, Inventory)
        .join(ProductSKU, ProductSKU.product_id == Product.id)
        .join(Inventory, Inventory.sku_id == ProductSKU.id)
        .where(ProductSKU.id == sku_id)
        .limit(1)
    )
    payload = row.first()
    if not payload:
        raise not_found("SKU not found")

    product, sku, inventory = payload
    if current_user.role != UserRole.ADMIN and (not product.is_active or not sku.is_active):
        raise not_found("SKU not found")

    conversions = (
        await db.scalars(
            select(SKUUnitConversion)
            .where(SKUUnitConversion.sku_id == sku.id)
            .options(selectinload(SKUUnitConversion.unit))
            .order_by(SKUUnitConversion.is_base_unit.desc(), SKUUnitConversion.to_base_factor.asc())
        )
    ).all()
    conversion_out = [
        UnitConversionOut(
            unit_code=item.unit.code,
            unit_name=item.unit.name,
            to_base_factor=item.to_base_factor,
            is_base_unit=item.is_base_unit,
        )
        for item in conversions
        if item.unit
    ]
    wholesale_price = sku.wholesale_price if current_user.role in {UserRole.ADMIN, UserRole.WHOLESALE} else None
    return ProductDetailOut(
        product_id=product.id,
        product_code=product.product_code,
        product_name=product.name,
        category=product.category,
        subcategory=product.subcategory,
        brand=product.brand,
        description=product.description,
        sku_id=sku.id,
        sku_name=sku.sku_name,
        sku_code=sku.sku_code,
        attrs=sku.attrs or {},
        min_wholesale_base_qty=sku.min_wholesale_base_qty,
        product_is_active=product.is_active,
        sku_is_active=sku.is_active,
        price=PriceViewOut(retail_price=sku.retail_price, wholesale_price=wholesale_price),
        on_hand_base_qty=inventory.on_hand_base_qty,
        reserved_base_qty=inventory.reserved_base_qty,
        sellable_stock=inventory.on_hand_base_qty - inventory.reserved_base_qty,
        conversions=conversion_out,
    )


@router.get("/options", response_model=list[ProductOptionOut])
async def list_product_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
    category: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=200, ge=1, le=1000),
    include_inactive: bool = Query(default=False),
) -> list[ProductOptionOut]:
    stmt = (
        select(ProductSKU)
        .join(Product, Product.id == ProductSKU.product_id)
        .join(Inventory, Inventory.sku_id == ProductSKU.id)
        .order_by(Product.id.desc(), ProductSKU.id.desc())
        .limit(limit)
        .options(
            selectinload(ProductSKU.product),
            selectinload(ProductSKU.inventory),
            selectinload(ProductSKU.unit_conversions).selectinload(SKUUnitConversion.unit),
        )
    )
    if not include_inactive or current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Product.is_active.is_(True), ProductSKU.is_active.is_(True))
    if keyword:
        like_kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            Product.name.ilike(like_kw)
            | ProductSKU.sku_name.ilike(like_kw)
            | ProductSKU.sku_code.ilike(like_kw)
        )
    if category:
        stmt = stmt.where(Product.category == category.strip())

    skus = (await db.scalars(stmt)).all()
    out: list[ProductOptionOut] = []
    for sku in skus:
        if not sku.product or not sku.inventory:
            continue
        conversions = sorted(
            sku.unit_conversions,
            key=lambda x: (x.unit.level if x.unit else 999, x.to_base_factor),
        )
        out.append(
            ProductOptionOut(
                sku_id=sku.id,
                product_code=sku.product.product_code,
                product_name=sku.product.name,
                category=sku.product.category,
                subcategory=sku.product.subcategory,
                sku_name=sku.sku_name,
                sku_code=sku.sku_code,
                min_wholesale_base_qty=sku.min_wholesale_base_qty,
                product_is_active=sku.product.is_active,
                sku_is_active=sku.is_active,
                on_hand_base_qty=sku.inventory.on_hand_base_qty,
                reserved_base_qty=sku.inventory.reserved_base_qty,
                sellable_stock=sku.inventory.on_hand_base_qty - sku.inventory.reserved_base_qty,
                conversions=[
                    UnitConversionOut(
                        unit_code=item.unit.code,
                        unit_name=item.unit.name,
                        to_base_factor=item.to_base_factor,
                        is_base_unit=item.is_base_unit,
                    )
                    for item in conversions
                    if item.unit
                ],
            )
        )
    return out


@router.get("/categories", response_model=list[ProductCategoryOut])
async def list_product_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[ProductCategoryOut]:
    return await _load_categories_tree(db, include_inactive=include_inactive)


@router.post("/categories", response_model=ProductCategoryOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_product_category(
    payload: ProductCategoryCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCategoryOut:
    parent = None
    if payload.parent_id is not None:
        parent = await db.get(ProductCategory, payload.parent_id)
        if not parent:
            raise not_found("parent category not found")
    code = _slugify_category_code(payload.code)
    exists = await db.scalar(
        select(ProductCategory.id).where(
            ProductCategory.parent_id == payload.parent_id,
            ProductCategory.name == payload.name.strip(),
        )
    )
    if exists:
        raise bad_request("category name already exists under the same parent")
    code_exists = await db.scalar(select(ProductCategory.id).where(ProductCategory.code == code))
    if code_exists:
        raise bad_request("category code already exists")
    item = ProductCategory(
        parent_id=parent.id if parent else None,
        name=payload.name.strip(),
        code=code,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize_category(item, {})


@router.patch("/categories/{category_id}", response_model=ProductCategoryOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def update_product_category(
    category_id: int,
    payload: ProductCategoryUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCategoryOut:
    item = await db.get(ProductCategory, category_id)
    if not item:
        raise not_found("category not found")
    update_data = payload.model_dump(exclude_unset=True)
    if "parent_id" in update_data:
        parent_id = update_data["parent_id"]
        if parent_id == item.id:
            raise bad_request("category cannot be its own parent")
        if parent_id is not None:
            parent = await db.get(ProductCategory, parent_id)
            if not parent:
                raise not_found("parent category not found")
        item.parent_id = parent_id
    if "name" in update_data:
        item.name = update_data["name"].strip()
    if "code" in update_data:
        item.code = _slugify_category_code(update_data["code"])
    if "sort_order" in update_data:
        item.sort_order = update_data["sort_order"]
    if "is_active" in update_data:
        item.is_active = update_data["is_active"]

    duplicate = await db.scalar(
        select(ProductCategory.id).where(
            ProductCategory.id != item.id,
            ProductCategory.parent_id == item.parent_id,
            ProductCategory.name == item.name,
        )
    )
    if duplicate:
        raise bad_request("category name already exists under the same parent")
    duplicate_code = await db.scalar(
        select(ProductCategory.id).where(
            ProductCategory.id != item.id,
            ProductCategory.code == item.code,
        )
    )
    if duplicate_code:
        raise bad_request("category code already exists")

    await db.commit()
    await db.refresh(item)
    return _serialize_category(item, {})


@router.delete("/categories/{category_id}", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def delete_product_category(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    item = await db.get(ProductCategory, category_id)
    if not item:
        raise not_found("category not found")
    child_exists = await db.scalar(select(ProductCategory.id).where(ProductCategory.parent_id == item.id))
    if child_exists:
        raise bad_request("category has child categories")
    linked_stmt = select(Product.id).limit(1)
    if item.parent_id is None:
        linked_stmt = linked_stmt.where(Product.category == item.name)
    else:
        linked_stmt = linked_stmt.where(Product.subcategory == item.name)
    linked = await db.scalar(linked_stmt)
    if linked:
        item.is_active = False
        await db.commit()
        return {"id": category_id, "deleted": False, "message": "category is in use and has been disabled"}
    await db.delete(item)
    await db.commit()
    return {"id": category_id, "deleted": True}


@router.patch(
    "/{sku_id}",
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def update_product_sku(
    sku_id: int,
    payload: ProductUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    sku = await db.scalar(
        select(ProductSKU)
        .where(ProductSKU.id == sku_id)
        .options(selectinload(ProductSKU.product))
    )
    if not sku or not sku.product:
        raise not_found("SKU not found")

    product = sku.product

    if payload.product_code and payload.product_code != product.product_code:
        code_exists = await db.scalar(
            select(Product.id).where(Product.product_code == payload.product_code, Product.id != product.id)
        )
        if code_exists:
            raise bad_request("product_code already exists")
        product.product_code = payload.product_code

    if payload.sku_code and payload.sku_code != sku.sku_code:
        sku_code_exists = await db.scalar(
            select(ProductSKU.id).where(ProductSKU.sku_code == payload.sku_code, ProductSKU.id != sku.id)
        )
        if sku_code_exists:
            raise bad_request("sku_code already exists")
        sku.sku_code = payload.sku_code

    if payload.name is not None:
        product.name = payload.name
    if payload.brand is not None:
        product.brand = payload.brand
    category_name = payload.category if payload.category is not None else product.category
    subcategory_name = payload.subcategory if payload.subcategory is not None else product.subcategory
    category_name, subcategory_name = await _validate_product_categories(db, category_name, subcategory_name)
    if payload.category is not None:
        product.category = category_name
    if payload.subcategory is not None:
        product.subcategory = subcategory_name
    if payload.description is not None:
        product.description = payload.description

    if payload.sku_name is not None:
        sku.sku_name = payload.sku_name
    if payload.attrs is not None:
        sku.attrs = payload.attrs
    if payload.retail_price is not None:
        sku.retail_price = payload.retail_price
    if payload.wholesale_price is not None:
        sku.wholesale_price = payload.wholesale_price
    if payload.min_wholesale_base_qty is not None:
        sku.min_wholesale_base_qty = payload.min_wholesale_base_qty

    await db.commit()
    return {
        "sku_id": sku.id,
        "product_id": product.id,
        "message": "updated",
    }


@router.patch(
    "/{sku_id}/status",
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def update_product_sku_status(
    sku_id: int,
    payload: ProductStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    sku = await db.scalar(
        select(ProductSKU)
        .where(ProductSKU.id == sku_id)
        .options(selectinload(ProductSKU.product).selectinload(Product.skus))
    )
    if not sku or not sku.product:
        raise not_found("SKU not found")

    sku.is_active = payload.is_active
    if payload.is_active:
        sku.product.is_active = True
    else:
        has_active_sku = any(item.id != sku.id and item.is_active for item in sku.product.skus)
        if not has_active_sku:
            sku.product.is_active = False

    await db.commit()
    return {
        "sku_id": sku.id,
        "product_id": sku.product.id,
        "sku_is_active": sku.is_active,
        "product_is_active": sku.product.is_active,
        "message": "status updated",
    }


@router.delete(
    "/{sku_id}",
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def deactivate_product_sku(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    sku = await db.scalar(
        select(ProductSKU)
        .where(ProductSKU.id == sku_id)
        .options(selectinload(ProductSKU.product).selectinload(Product.skus))
    )
    if not sku or not sku.product:
        raise not_found("SKU not found")

    sku.is_active = False
    has_active_sku = any(item.id != sku.id and item.is_active for item in sku.product.skus)
    if not has_active_sku:
        sku.product.is_active = False

    await db.commit()
    return {
        "sku_id": sku.id,
        "product_id": sku.product.id,
        "sku_is_active": sku.is_active,
        "product_is_active": sku.product.is_active,
        "message": "deactivated",
    }


@router.post(
    "/{sku_id}/inventory-adjust",
    dependencies=[Depends(require_roles({UserRole.ADMIN}))],
)
async def inventory_adjust(
    sku_id: int,
    payload: InventoryAdjustIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inventory = await adjust_inventory(db=db, sku_id=sku_id, delta_base_qty=payload.delta_base_qty, note=payload.note)
    await db.commit()
    return {
        "sku_id": sku_id,
        "on_hand_base_qty": inventory.on_hand_base_qty,
        "reserved_base_qty": inventory.reserved_base_qty,
        "version": inventory.version,
    }


@router.post("/deduct")
async def deduct_stock(
    payload: StockDeductIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    sku_exists = await db.scalar(select(ProductSKU.id).where(ProductSKU.id == payload.sku_id))
    if not sku_exists:
        raise not_found("SKU not found")

    inventory = await deduct_by_unit(
        db=db,
        sku_id=payload.sku_id,
        unit_code=payload.unit_code,
        quantity=payload.quantity,
        user=current_user,
        order_no=payload.order_no,
    )
    await db.commit()
    return {
        "sku_id": payload.sku_id,
        "remaining_on_hand_base_qty": inventory.on_hand_base_qty,
        "version": inventory.version,
    }
