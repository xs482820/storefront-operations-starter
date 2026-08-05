from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SKUType, UserRole, WholesaleApplicationStatus


class ProductCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_name: str | None = Field(default=None, max_length=128)
    product_code: str = Field(min_length=1, max_length=64)
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    image_urls: list[str] = Field(default_factory=list)
    spec_dim_1_name: str = Field(default="颜色/形状", min_length=1, max_length=32)
    spec_dim_2_name: str = Field(default="尺码/大小", min_length=1, max_length=32)
    supports_retail: bool = True
    supports_wholesale: bool = False
    has_dual_price: bool = True


class ProductCategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class ProductCategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    model_name: str | None = Field(default=None, max_length=128)
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    image_urls: list[str] | None = None
    spec_dim_1_name: str | None = Field(default=None, min_length=1, max_length=32)
    spec_dim_2_name: str | None = Field(default=None, min_length=1, max_length=32)
    supports_retail: bool | None = None
    supports_wholesale: bool | None = None
    has_dual_price: bool | None = None
    is_active: bool | None = None


class BulkSkuCreateIn(BaseModel):
    product_id: int
    sku_type: SKUType
    spec_values_1: list[str] = Field(min_length=1)
    spec_values_2: list[str] = Field(min_length=1)
    online_stock: int = Field(ge=0)
    retail_price: Decimal = Field(ge=0)
    wholesale_price: Decimal = Field(ge=0)
    min_sale_qty: int = Field(default=1, ge=1)
    min_wholesale_qty: int = Field(default=1, ge=1)
    is_mixed_pack: bool = False
    mixed_pack_note: str | None = Field(default=None, max_length=255)


class SKUUpdateIn(BaseModel):
    spec_value_1: str | None = Field(default=None, max_length=64)
    spec_value_2: str | None = Field(default=None, max_length=64)
    sku_label: str | None = Field(default=None, max_length=128)
    online_stock: int | None = Field(default=None, ge=0)
    retail_price: Decimal | None = Field(default=None, ge=0)
    wholesale_price: Decimal | None = Field(default=None, ge=0)
    min_sale_qty: int | None = Field(default=None, ge=1)
    min_wholesale_qty: int | None = Field(default=None, ge=1)
    is_mixed_pack: bool | None = None
    mixed_pack_note: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class ProductSkuSyncRow(BaseModel):
    spec_value_1: str
    spec_value_2: str
    retail_price: Decimal = Field(ge=0)
    wholesale_price: Decimal = Field(ge=0)
    min_wholesale_qty: int = Field(default=1, ge=1)
    online_stock: int = Field(default=0, ge=0)


class ProductSkuSyncIn(BaseModel):
    product_id: int
    skus: list[ProductSkuSyncRow]


class WholesaleApplicationReviewIn(BaseModel):
    status: WholesaleApplicationStatus
    review_note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_reject_reason(self) -> "WholesaleApplicationReviewIn":
        if self.status == WholesaleApplicationStatus.REJECTED and not (self.review_note or "").strip():
            raise ValueError("review_note is required when rejecting")
        return self


class UserRuntimeStateUpdateIn(BaseModel):
    is_blacklisted: bool | None = None
    is_flagged: bool | None = None


class UserNoteUpdateIn(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class UserRoleChangeIn(BaseModel):
    role: UserRole
    company_name: str | None = Field(default=None, max_length=128)
    store_name: str | None = Field(default=None, max_length=128)
    business_type: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)


class StorefrontMarqueeNoticeIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(default="", max_length=500)
    action_label: str = Field(default="查看", min_length=1, max_length=24)
    action_type: str = Field(default="none", max_length=32)
    action_value: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)
    starts_at: str | None = None
    ends_at: str | None = None


class StorefrontMarqueeNoticeOut(StorefrontMarqueeNoticeIn):
    id: int
    created_at: str
    updated_at: str


class StorefrontMarqueeNoticeListIn(BaseModel):
    notices: list[StorefrontMarqueeNoticeIn] = Field(default_factory=list, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    business_license_url: str | None = Field(default=None, max_length=255)
    admin_confirm_password: str | None = Field(default=None, max_length=128)


class EmployeeAccountCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)
    admin_confirm_password: str = Field(min_length=6, max_length=128)


class EmployeeAccountUpdateIn(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str | None = Field(default=None, min_length=12, max_length=128)
    is_active: bool | None = None
    admin_confirm_password: str = Field(min_length=6, max_length=128)


class DeleteConfirmationIn(BaseModel):
    confirmation_text: str = Field(min_length=1, max_length=32)


class OrderAdjustmentIn(BaseModel):
    shipping_recipient: str | None = Field(default=None, max_length=64)
    shipping_phone: str | None = Field(default=None, max_length=32)
    shipping_address: str | None = Field(default=None, max_length=255)
    customer_note: str | None = Field(default=None, max_length=255)
    internal_note: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=255)


class OrderTerminationIn(BaseModel):
    reason: str = Field(min_length=1, max_length=255)
    disposition: str | None = Field(default=None, max_length=255)
    internal_note: str | None = Field(default=None, max_length=1000)


class AftersaleNotesIn(BaseModel):
    customer_note: str | None = Field(default=None, max_length=255)
    internal_note: str | None = Field(default=None, max_length=1000)
