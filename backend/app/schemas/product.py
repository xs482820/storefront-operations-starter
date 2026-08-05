from decimal import Decimal

from pydantic import BaseModel, Field


class UnitConversionIn(BaseModel):
    unit_code: str = Field(min_length=1, max_length=32)
    unit_name: str = Field(min_length=1, max_length=32)
    unit_level: int = Field(ge=1, le=10)
    to_base_factor: int = Field(gt=0)
    is_base_unit: bool = False


class SKUCreateIn(BaseModel):
    sku_code: str = Field(min_length=1, max_length=64)
    sku_name: str = Field(min_length=1, max_length=128)
    attrs: dict = Field(default_factory=dict)
    retail_price: Decimal = Field(ge=0)
    wholesale_price: Decimal = Field(ge=0)
    min_wholesale_base_qty: int = Field(ge=1, default=1)
    conversions: list[UnitConversionIn]


class ProductCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    subcategory: str | None = Field(default=None, max_length=64)
    product_code: str = Field(min_length=1, max_length=64)
    description: str | None = None
    skus: list[SKUCreateIn]


class ProductQuickCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    subcategory: str | None = Field(default=None, max_length=64)
    product_code: str = Field(min_length=1, max_length=64)
    sku_code: str = Field(min_length=1, max_length=64)
    sku_name: str = Field(min_length=1, max_length=128)
    retail_price: Decimal = Field(ge=0)
    wholesale_price: Decimal = Field(ge=0)
    min_wholesale_base_qty: int = Field(default=1, ge=1)
    box_to_piece_factor: int = Field(default=12, ge=1, le=100000)
    attrs: dict = Field(default_factory=dict)


class ProductQuickCreateOut(BaseModel):
    product_id: int
    sku_id: int
    product_code: str
    sku_code: str
    message: str


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    subcategory: str | None = Field(default=None, max_length=64)
    product_code: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1000)

    sku_name: str | None = Field(default=None, min_length=1, max_length=128)
    sku_code: str | None = Field(default=None, min_length=1, max_length=64)
    attrs: dict | None = None
    retail_price: Decimal | None = Field(default=None, ge=0)
    wholesale_price: Decimal | None = Field(default=None, ge=0)
    min_wholesale_base_qty: int | None = Field(default=None, ge=1)


class ProductStatusUpdateIn(BaseModel):
    is_active: bool


class ProductCategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    parent_id: int | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class ProductCategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    parent_id: int | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None


class ProductCategoryOut(BaseModel):
    id: int
    name: str
    code: str
    parent_id: int | None = None
    sort_order: int
    is_active: bool
    children: list["ProductCategoryOut"] = Field(default_factory=list)


class PriceViewOut(BaseModel):
    retail_price: Decimal
    wholesale_price: Decimal | None = None


class ProductListOut(BaseModel):
    product_id: int
    product_code: str
    sku_id: int
    product_name: str
    category: str | None = None
    subcategory: str | None = None
    sku_name: str
    sku_code: str
    attrs: dict
    min_wholesale_base_qty: int
    product_is_active: bool = True
    sku_is_active: bool = True
    price: PriceViewOut
    on_hand_base_qty: int
    reserved_base_qty: int
    sellable_stock: int
    conversions: list["UnitConversionOut"] = Field(default_factory=list)
    description: str | None = None


class UnitConversionOut(BaseModel):
    unit_code: str
    unit_name: str
    to_base_factor: int
    is_base_unit: bool


class ProductOptionOut(BaseModel):
    sku_id: int
    product_code: str
    product_name: str
    category: str | None = None
    subcategory: str | None = None
    sku_name: str
    sku_code: str
    min_wholesale_base_qty: int
    product_is_active: bool = True
    sku_is_active: bool = True
    on_hand_base_qty: int
    reserved_base_qty: int
    sellable_stock: int
    conversions: list[UnitConversionOut]


class ProductDetailOut(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    description: str | None = None
    sku_id: int
    sku_name: str
    sku_code: str
    attrs: dict
    min_wholesale_base_qty: int
    product_is_active: bool = True
    sku_is_active: bool = True
    price: PriceViewOut
    on_hand_base_qty: int
    reserved_base_qty: int
    sellable_stock: int
    conversions: list[UnitConversionOut]


class InventoryAdjustIn(BaseModel):
    delta_base_qty: int
    note: str | None = Field(default=None, max_length=255)


class StockDeductIn(BaseModel):
    sku_id: int
    unit_code: str
    quantity: int = Field(gt=0)
    order_no: str | None = Field(default=None, max_length=40)


ProductCategoryOut.model_rebuild()
ProductListOut.model_rebuild()
ProductDetailOut.model_rebuild()
