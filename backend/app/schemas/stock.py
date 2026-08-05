from pydantic import BaseModel, Field, model_validator

from app.models.enums import StockDocumentStatus, StockDocumentType


class StockOperationIn(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0, description="按选择单位录入的数量")
    unit_code: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=255)


class StockAdjustBaseIn(BaseModel):
    sku_id: int
    delta_base_qty: int
    note: str | None = Field(default=None, max_length=255)


class StocktakeIn(BaseModel):
    sku_id: int
    counted_base_qty: int = Field(ge=0, description="盘点后的实际最小单位库存")
    note: str | None = Field(default=None, max_length=255)


class StockLedgerOut(BaseModel):
    id: int
    sku_id: int
    delta_base_qty: int
    change_type: str
    ref_order_no: str | None = None
    note: str | None = None
    created_at: str


class StockDocumentItemIn(BaseModel):
    sku_id: int
    unit_code: str | None = Field(default=None, min_length=1, max_length=32)
    quantity: int | None = Field(default=None, gt=0)
    delta_base_qty: int | None = None
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_item(self) -> "StockDocumentItemIn":
        if self.delta_base_qty is None and (self.quantity is None or not self.unit_code):
            raise ValueError("either delta_base_qty or quantity + unit_code is required")
        return self


class StockDocumentCreateIn(BaseModel):
    doc_type: StockDocumentType
    source: str | None = Field(default="admin_console", max_length=64)
    note: str | None = Field(default=None, max_length=255)
    items: list[StockDocumentItemIn] = Field(min_length=1)


class StockDocumentItemOut(BaseModel):
    id: int
    sku_id: int
    unit_id: int | None
    quantity: int | None
    delta_base_qty: int
    note: str | None = None


class StockDocumentOut(BaseModel):
    id: int
    doc_no: str
    doc_type: StockDocumentType
    status: StockDocumentStatus
    operator_id: int | None
    source: str | None = None
    note: str | None = None
    total_items: int
    total_base_qty: int
    created_at: str
    items: list[StockDocumentItemOut] = []


class StockMovementSummaryOut(BaseModel):
    sku_id: int
    sku_code: str
    sku_name: str
    product_name: str
    outbound_base_qty: int
    inbound_base_qty: int
    net_change_base_qty: int


class StockOverviewOut(BaseModel):
    total_on_hand_base_qty: int
    total_reserved_base_qty: int
    low_stock_skus: int
    recent_document_count: int


class StockReserveIn(BaseModel):
    sku_id: int
    reserve_base_qty: int = Field(gt=0)
    order_no: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=255)


class StockReleaseIn(BaseModel):
    sku_id: int
    release_base_qty: int = Field(gt=0)
    order_no: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=255)


class StockSkuSnapshotOut(BaseModel):
    sku_id: int
    sku_code: str
    sku_name: str
    product_name: str
    on_hand_base_qty: int
    reserved_base_qty: int
    available_base_qty: int
    version: int


class StockTurnoverOut(BaseModel):
    sku_id: int
    sku_code: str
    sku_name: str
    product_name: str
    outbound_base_qty: int
    inbound_base_qty: int
    net_change_base_qty: int
