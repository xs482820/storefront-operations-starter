from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import bad_request, not_found
from app.db.session import get_db
from app.models.enums import StockChangeType, StockDocumentType, UserRole
from app.models.product import Inventory, Product, ProductSKU
from app.models.stock import StockDocument, StockLedger
from app.models.user import User
from app.schemas.stock import (
    StockAdjustBaseIn,
    StockDocumentCreateIn,
    StockDocumentItemIn,
    StockDocumentItemOut,
    StockDocumentOut,
    StockLedgerOut,
    StockMovementSummaryOut,
    StockOverviewOut,
    StockReleaseIn,
    StockReserveIn,
    StockSkuSnapshotOut,
    StockOperationIn,
    StockTurnoverOut,
    StocktakeIn,
)
from app.services.inventory import (
    apply_stock_document,
    build_stocktake_document,
    lock_inventory_row,
    release_reserved_by_base,
    reserve_by_base,
)

router = APIRouter(prefix="/stock", tags=["stock"])


def _serialize_document(document: StockDocument) -> StockDocumentOut:
    return StockDocumentOut(
        id=document.id,
        doc_no=document.doc_no,
        doc_type=document.doc_type,
        status=document.status,
        operator_id=document.operator_id,
        source=document.source,
        note=document.note,
        total_items=document.total_items,
        total_base_qty=document.total_base_qty,
        created_at=document.created_at.isoformat(),
        items=[
            StockDocumentItemOut(
                id=item.id,
                sku_id=item.sku_id,
                unit_id=item.unit_id,
                quantity=item.quantity,
                delta_base_qty=item.delta_base_qty,
                note=item.note,
            )
            for item in document.items
        ],
    )


@router.get("/ledgers", response_model=list[StockLedgerOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_stock_ledgers(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[StockLedgerOut]:
    ledgers = (
        await db.scalars(select(StockLedger).order_by(desc(StockLedger.id)).limit(limit))
    ).all()
    return [
        StockLedgerOut(
            id=item.id,
            sku_id=item.sku_id,
            delta_base_qty=item.delta_base_qty,
            change_type=item.change_type.value,
            ref_order_no=item.ref_order_no,
            note=item.note,
            created_at=item.created_at.isoformat(),
        )
        for item in ledgers
    ]


@router.get("/overview", response_model=StockOverviewOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StockOverviewOut:
    total_on_hand = await db.scalar(select(func.coalesce(func.sum(Inventory.on_hand_base_qty), 0))) or 0
    total_reserved = await db.scalar(select(func.coalesce(func.sum(Inventory.reserved_base_qty), 0))) or 0
    low_stock_skus = await db.scalar(select(func.count(Inventory.id)).where(Inventory.on_hand_base_qty <= 10)) or 0
    recent_document_count = await db.scalar(select(func.count(StockDocument.id))) or 0
    return StockOverviewOut(
        total_on_hand_base_qty=int(total_on_hand),
        total_reserved_base_qty=int(total_reserved),
        low_stock_skus=int(low_stock_skus),
        recent_document_count=int(recent_document_count),
    )


@router.get("/movement-summary", response_model=list[StockMovementSummaryOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_movement_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[StockMovementSummaryOut]:
    outbound_case = case((StockLedger.delta_base_qty < 0, -StockLedger.delta_base_qty), else_=0)
    inbound_case = case((StockLedger.delta_base_qty > 0, StockLedger.delta_base_qty), else_=0)
    rows = (
        await db.execute(
            select(
                ProductSKU.id,
                ProductSKU.sku_code,
                ProductSKU.sku_name,
                Product.name,
                func.coalesce(func.sum(outbound_case), 0).label("outbound_base_qty"),
                func.coalesce(func.sum(inbound_case), 0).label("inbound_base_qty"),
                func.coalesce(func.sum(StockLedger.delta_base_qty), 0).label("net_change_base_qty"),
            )
            .join(StockLedger, StockLedger.sku_id == ProductSKU.id)
            .join(Product, Product.id == ProductSKU.product_id)
            .group_by(ProductSKU.id, ProductSKU.sku_code, ProductSKU.sku_name, Product.name)
            .order_by(desc(func.coalesce(func.sum(outbound_case), 0)), desc(ProductSKU.id))
            .limit(limit)
        )
    ).all()
    return [
        StockMovementSummaryOut(
            sku_id=row[0],
            sku_code=row[1],
            sku_name=row[2],
            product_name=row[3],
            outbound_base_qty=int(row[4]),
            inbound_base_qty=int(row[5]),
            net_change_base_qty=int(row[6]),
        )
        for row in rows
    ]


@router.get("/documents", response_model=list[StockDocumentOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_stock_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    doc_type: StockDocumentType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[StockDocumentOut]:
    stmt = (
        select(StockDocument)
        .options(selectinload(StockDocument.items))
        .order_by(desc(StockDocument.id))
        .limit(limit)
    )
    if doc_type:
        stmt = stmt.where(StockDocument.doc_type == doc_type)
    documents = (await db.scalars(stmt)).all()
    return [_serialize_document(item) for item in documents]


@router.get("/documents/{doc_no}", response_model=StockDocumentOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def get_stock_document(
    doc_no: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StockDocumentOut:
    document = await db.scalar(
        select(StockDocument)
        .options(selectinload(StockDocument.items))
        .where(StockDocument.doc_no == doc_no)
    )
    if not document:
        raise not_found("stock document not found")
    return _serialize_document(document)


@router.post("/documents", response_model=StockDocumentOut, dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def create_stock_document(
    payload: StockDocumentCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StockDocumentOut:
    document = await apply_stock_document(db=db, payload=payload, operator=current_user)
    await db.commit()
    document = await db.scalar(
        select(StockDocument)
        .options(selectinload(StockDocument.items))
        .where(StockDocument.id == document.id)
    )
    if not document:
        raise not_found("stock document not found")
    return _serialize_document(document)


@router.post("/inbound", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_inbound(
    payload: StockOperationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    document = await apply_stock_document(
        db=db,
        payload=StockDocumentCreateIn(
            doc_type=StockDocumentType.INBOUND,
            note=payload.note or "manual inbound",
            items=[StockDocumentItemIn(sku_id=payload.sku_id, quantity=payload.quantity, unit_code=payload.unit_code, note=payload.note)],
        ),
        operator=current_user,
    )
    await db.commit()
    return {"doc_no": document.doc_no, "sku_id": payload.sku_id, "total_base_qty": document.total_base_qty}


@router.post("/outbound", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_outbound(
    payload: StockOperationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    document = await apply_stock_document(
        db=db,
        payload=StockDocumentCreateIn(
            doc_type=StockDocumentType.OUTBOUND,
            note=payload.note or "manual outbound",
            items=[StockDocumentItemIn(sku_id=payload.sku_id, quantity=payload.quantity, unit_code=payload.unit_code, note=payload.note)],
        ),
        operator=current_user,
    )
    await db.commit()
    return {"doc_no": document.doc_no, "sku_id": payload.sku_id, "total_base_qty": document.total_base_qty}


@router.post("/adjust", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_adjust(
    payload: StockAdjustBaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if payload.delta_base_qty == 0:
        raise bad_request("delta_base_qty cannot be 0")
    document = await apply_stock_document(
        db=db,
        payload=StockDocumentCreateIn(
            doc_type=StockDocumentType.ADJUSTMENT,
            note=payload.note or "manual adjustment",
            items=[StockDocumentItemIn(sku_id=payload.sku_id, delta_base_qty=payload.delta_base_qty, note=payload.note)],
        ),
        operator=current_user,
    )
    await db.commit()
    return {"doc_no": document.doc_no, "sku_id": payload.sku_id, "total_base_qty": document.total_base_qty}


@router.post("/stocktake", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stocktake(
    payload: StocktakeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    document = await build_stocktake_document(
        db=db,
        sku_id=payload.sku_id,
        counted_base_qty=payload.counted_base_qty,
        note=payload.note or "manual stocktake",
        operator=current_user,
    )
    await db.commit()
    return {"doc_no": document.doc_no, "sku_id": payload.sku_id, "total_base_qty": document.total_base_qty}


@router.post("/loss", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_loss(
    payload: StockOperationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    document = await apply_stock_document(
        db=db,
        payload=StockDocumentCreateIn(
            doc_type=StockDocumentType.OUTBOUND,
            source="loss",
            note=payload.note or "stock loss",
            items=[StockDocumentItemIn(sku_id=payload.sku_id, quantity=payload.quantity, unit_code=payload.unit_code, note=payload.note or "loss")],
        ),
        operator=current_user,
    )
    await db.commit()
    return {"doc_no": document.doc_no, "sku_id": payload.sku_id, "total_base_qty": document.total_base_qty}


@router.post("/reserve", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def reserve_stock(
    payload: StockReserveIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inventory = await reserve_by_base(
        db=db,
        sku_id=payload.sku_id,
        base_qty=payload.reserve_base_qty,
        note=payload.note,
        order_no=payload.order_no,
    )
    await db.commit()
    return {
        "sku_id": payload.sku_id,
        "on_hand_base_qty": inventory.on_hand_base_qty,
        "reserved_base_qty": inventory.reserved_base_qty,
        "available_base_qty": inventory.on_hand_base_qty - inventory.reserved_base_qty,
    }


@router.post("/release", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def release_stock(
    payload: StockReleaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inventory = await release_reserved_by_base(
        db=db,
        sku_id=payload.sku_id,
        base_qty=payload.release_base_qty,
        note=payload.note,
        order_no=payload.order_no,
    )
    await db.commit()
    return {
        "sku_id": payload.sku_id,
        "on_hand_base_qty": inventory.on_hand_base_qty,
        "reserved_base_qty": inventory.reserved_base_qty,
        "available_base_qty": inventory.on_hand_base_qty - inventory.reserved_base_qty,
    }


@router.get("/snapshots", response_model=list[StockSkuSnapshotOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def list_stock_snapshots(
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(default=None, min_length=1, max_length=64),
    only_low_stock: bool = Query(default=False),
    low_stock_threshold: int = Query(default=10, ge=0, le=1000000),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[StockSkuSnapshotOut]:
    stmt = (
        select(
            ProductSKU.id,
            ProductSKU.sku_code,
            ProductSKU.sku_name,
            Product.name,
            Inventory.on_hand_base_qty,
            Inventory.reserved_base_qty,
            Inventory.version,
        )
        .join(Product, Product.id == ProductSKU.product_id)
        .join(Inventory, Inventory.sku_id == ProductSKU.id)
        .order_by(desc(Inventory.on_hand_base_qty), ProductSKU.id.asc())
        .limit(limit)
    )
    if keyword:
        like_kw = f"%{keyword}%"
        stmt = stmt.where(
            ProductSKU.sku_code.ilike(like_kw)
            | ProductSKU.sku_name.ilike(like_kw)
            | Product.name.ilike(like_kw)
        )
    if only_low_stock:
        stmt = stmt.where((Inventory.on_hand_base_qty - Inventory.reserved_base_qty) <= low_stock_threshold)

    rows = (await db.execute(stmt)).all()
    return [
        StockSkuSnapshotOut(
            sku_id=row[0],
            sku_code=row[1],
            sku_name=row[2],
            product_name=row[3],
            on_hand_base_qty=row[4],
            reserved_base_qty=row[5],
            available_base_qty=row[4] - row[5],
            version=row[6],
        )
        for row in rows
    ]


@router.get("/turnover", response_model=list[StockTurnoverOut], dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_turnover(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[StockTurnoverOut]:
    since = datetime.now(UTC) - timedelta(days=days)
    outbound_case = case((StockLedger.delta_base_qty < 0, -StockLedger.delta_base_qty), else_=0)
    inbound_case = case((StockLedger.delta_base_qty > 0, StockLedger.delta_base_qty), else_=0)
    rows = (
        await db.execute(
            select(
                ProductSKU.id,
                ProductSKU.sku_code,
                ProductSKU.sku_name,
                Product.name,
                func.coalesce(func.sum(outbound_case), 0).label("outbound_base_qty"),
                func.coalesce(func.sum(inbound_case), 0).label("inbound_base_qty"),
                func.coalesce(func.sum(StockLedger.delta_base_qty), 0).label("net_change_base_qty"),
            )
            .join(Product, Product.id == ProductSKU.product_id)
            .join(StockLedger, StockLedger.sku_id == ProductSKU.id)
            .where(StockLedger.created_at >= since)
            .group_by(ProductSKU.id, ProductSKU.sku_code, ProductSKU.sku_name, Product.name)
            .order_by(desc(func.coalesce(func.sum(outbound_case), 0)), ProductSKU.id.asc())
            .limit(limit)
        )
    ).all()
    return [
        StockTurnoverOut(
            sku_id=row[0],
            sku_code=row[1],
            sku_name=row[2],
            product_name=row[3],
            outbound_base_qty=int(row[4]),
            inbound_base_qty=int(row[5]),
            net_change_base_qty=int(row[6]),
        )
        for row in rows
    ]


@router.get("/{sku_id}/snapshot", dependencies=[Depends(require_roles({UserRole.ADMIN}))])
async def stock_snapshot(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    inventory = await lock_inventory_row(db, sku_id)
    on_hand_base_qty = inventory.on_hand_base_qty
    reserved_base_qty = inventory.reserved_base_qty
    version = inventory.version
    available = on_hand_base_qty - reserved_base_qty
    await db.rollback()
    if available < 0:
        raise bad_request("inventory snapshot invalid")
    return {
        "sku_id": sku_id,
        "on_hand_base_qty": on_hand_base_qty,
        "reserved_base_qty": reserved_base_qty,
        "available_base_qty": available,
        "version": version,
    }
