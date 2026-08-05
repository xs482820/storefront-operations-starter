from decimal import Decimal
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import AfterSaleReason, PaymentMethod


class CustomerProductSKUOut(BaseModel):
    sku_id: int
    sku_code: str
    sku_type: str
    spec_value_1: str | None = None
    spec_value_2: str | None = None
    sku_label: str | None = None
    online_stock: int
    retail_price: Decimal
    wholesale_price: Decimal | None = None
    min_sale_qty: int
    min_wholesale_qty: int
    is_mixed_pack: bool
    mixed_pack_note: str | None = None


class CustomerProductOut(BaseModel):
    product_id: int
    product_code: str
    name: str
    model_name: str | None = None
    brand: str | None = None
    category: str | None = None
    description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    spec_dim_1_name: str
    spec_dim_2_name: str
    skus: list[CustomerProductSKUOut]
    is_favorited: bool = False


class CustomerMeOut(BaseModel):
    user_id: int
    username: str
    role: str
    display_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    company_name: str | None = None
    store_name: str | None = None
    contact_name: str | None = None
    address: str | None = None
    business_license_url: str | None = None
    is_verified_wholesale: bool = False
    wechat_bound: bool = False
    employee_mode: str = "shopping"
    miniapp_notification_enabled: bool = False
    miniapp_notification_event_keys: list[str] = Field(default_factory=list)
    miniapp_notification_updated_at: str | None = None


class CustomerMeUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=20)
    avatar_url: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=128)
    store_name: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)
    employee_mode: str | None = Field(default=None, max_length=16)
    miniapp_notification_enabled: bool | None = None
    miniapp_notification_event_keys: list[str] | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned != value:
            raise ValueError("display_name must not be blank")
        if not re.fullmatch(r"[A-Za-z\u4E00-\u9FFF]+", cleaned):
            raise ValueError("display_name must contain only Chinese or English letters")
        return cleaned

    @model_validator(mode="after")
    def validate_employee_mode(self) -> "CustomerMeUpdateIn":
        if self.employee_mode is None:
            return self
        if self.employee_mode not in {"shopping", "workbench"}:
            raise ValueError("employee_mode must be shopping or workbench")
        return self

    @model_validator(mode="after")
    def validate_notification_event_keys(self) -> "CustomerMeUpdateIn":
        if self.miniapp_notification_event_keys is None:
            return self
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in self.miniapp_notification_event_keys:
            key = str(item).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            cleaned.append(key[:64])
            if len(cleaned) >= 20:
                break
        self.miniapp_notification_event_keys = cleaned
        return self


class CustomerOrderItemIn(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)


class CustomerOrderCreateIn(BaseModel):
    items: list[CustomerOrderItemIn] = Field(min_length=1)
    shipping_channel: str = Field(default="express", max_length=16)
    pricing_mode: Literal["retail", "wholesale"] | None = Field(default=None)
    shipping_recipient: str | None = Field(default=None, max_length=64)
    shipping_phone: str | None = Field(default=None, max_length=32)
    shipping_province: str | None = Field(default=None, max_length=64)
    shipping_city: str | None = Field(default=None, max_length=64)
    shipping_district: str | None = Field(default=None, max_length=64)
    shipping_address: str | None = Field(default=None, max_length=255)
    payment_method: PaymentMethod = PaymentMethod.WECHAT_PAY
    note: str | None = Field(default=None, max_length=255)


class CustomerOrderItemOut(BaseModel):
    product_id: int | None = None
    sku_id: int
    product_name: str
    sku_code: str
    sku_type: str
    spec_value_1: str | None = None
    spec_value_2: str | None = None
    product_image_url: str | None = None
    quantity: int
    unit_price: Decimal
    line_amount: Decimal


class CustomerOrderOut(BaseModel):
    order_id: int
    order_no: str
    status: str
    buyer_role: str
    original_amount: Decimal
    shipping_fee: Decimal
    payable_amount: Decimal
    payment_method: str
    shipping_mode: str | None = None
    shipping_proof_url: str | None = None
    shipping_recipient: str | None = None
    shipping_phone: str | None = None
    shipping_address: str | None = None
    note: str | None = None
    cancellation_reason: str | None = None
    cancellation_source: str | None = None
    termination_reason: str | None = None
    termination_disposition: str | None = None
    created_at: str
    paid_at: str | None = None
    shipped_at: str | None = None
    delivery_signed_at: str | None = None
    completed_at: str | None = None
    canceled_at: str | None = None
    terminated_at: str | None = None
    items: list[CustomerOrderItemOut]

    # 计算字段，减少前端逻辑
    can_cancel: bool = False
    can_confirm_receipt: bool = False
    can_aftersale: bool = False
    can_delete: bool = False


class WholesaleApplicationCreateIn(BaseModel):
    company_name: str | None = Field(default=None, max_length=128)
    store_name: str | None = Field(default=None, max_length=128)
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    business_license_url: str | None = Field(default=None, max_length=255)
    remark: str | None = Field(default=None, max_length=255)


class WholesaleApplicationOut(BaseModel):
    id: int
    status: str
    effective_status: str
    company_name: str | None = None
    store_name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    business_license_url: str | None = None
    remark: str | None = None
    review_note: str | None = None
    created_at: str


class CustomerAfterSaleCreateIn(BaseModel):
    order_id: int
    reason: AfterSaleReason
    requested_amount: Decimal | None = Field(default=None, ge=0)
    custom_reason_text: str | None = Field(default=None, max_length=255)
    chat_proof_url: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_other_reason(self) -> "CustomerAfterSaleCreateIn":
        if self.reason == AfterSaleReason.OTHER and not (self.custom_reason_text or "").strip():
            raise ValueError("custom_reason_text is required when reason is other")
        return self


class CustomerAfterSaleOut(BaseModel):
    id: int
    order_id: int
    order_no: str | None = None
    reason: str
    custom_reason_text: str | None = None
    process_type: str | None = None
    refund_amount: Decimal | None = None
    chat_proof_url: str | None = None
    status: str
    note: str | None = None
    created_at: str


class WechatPayCreateOut(BaseModel):
    payment_no: str
    order_no: str
    status: str
    amount: str
    prepay_id: str | None = None
    jsapi_params: dict | None = None
    message: str


class CustomerCartItemOut(BaseModel):
    product_id: int
    sku_id: int
    sku_type: str
    product_name: str
    sku_code: str
    spec_value_1: str | None = None
    spec_value_2: str | None = None
    quantity: int
    online_stock: int
    retail_price: Decimal
    wholesale_price: Decimal | None = None
    min_sale_qty: int
    min_wholesale_qty: int
    selected: bool
    delisted: bool = False
    product_image_url: str | None = None


class CustomerFavoriteOut(BaseModel):
    id: int
    product_id: int
    created_at: str
    product: CustomerProductOut


class CustomerCartUpsertIn(BaseModel):
    quantity: int = Field(ge=1)
    selected: bool = True


class CustomerCartBatchSyncItemIn(BaseModel):
    sku_id: int
    quantity: int = Field(ge=1)
    selected: bool = True


class CustomerCartBatchSyncIn(BaseModel):
    items: list[CustomerCartBatchSyncItemIn] = Field(default_factory=list)
    replace_existing: bool = True


class CustomerCartBatchSyncIssueOut(BaseModel):
    sku_id: int | None = None
    product_name: str | None = None
    reason: str


class CustomerCartBatchSyncOut(BaseModel):
    synced_count: int
    removed_count: int
    cart_items: list[CustomerCartItemOut] = Field(default_factory=list)
    issues: list[CustomerCartBatchSyncIssueOut] = Field(default_factory=list)


class CustomerCategoryOut(BaseModel):
    code: str
    name: str
    product_count: int


class CustomerCheckoutPreviewItemOut(BaseModel):
    product_id: int
    sku_id: int
    product_name: str
    sku_code: str
    sku_type: str
    spec_value_1: str | None = None
    spec_value_2: str | None = None
    quantity: int
    unit_price: Decimal
    line_amount: Decimal
    online_stock: int
    min_required_qty: int
    product_image_url: str | None = None


class CustomerCheckoutPreviewIn(BaseModel):
    items: list[CustomerOrderItemIn] = Field(min_length=1)
    shipping_channel: str = Field(default="express", max_length=16)
    pricing_mode: Literal["retail", "wholesale"] | None = Field(default=None)
    payment_method: PaymentMethod = PaymentMethod.WECHAT_PAY
    shipping_recipient: str | None = Field(default=None, max_length=64)
    shipping_phone: str | None = Field(default=None, max_length=32)
    shipping_province: str | None = Field(default=None, max_length=64)
    shipping_city: str | None = Field(default=None, max_length=64)
    shipping_district: str | None = Field(default=None, max_length=64)
    shipping_address: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)


class CustomerCheckoutPreviewOut(BaseModel):
    buyer_role: str
    pricing_mode: str
    shipping_channel: str
    payment_method: str
    merchandise_amount: Decimal
    shipping_fee: Decimal
    payable_amount: Decimal
    free_shipping_threshold: Decimal
    shortfall_to_free_shipping: Decimal
    can_submit: bool
    issues: list[str] = Field(default_factory=list)
    items: list[CustomerCheckoutPreviewItemOut] = Field(default_factory=list)


class CustomerAddressIn(BaseModel):
    contact_name: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)
    region: str = Field(min_length=1, max_length=128)
    detail: str = Field(min_length=1, max_length=255)
    tag: str = Field(default="常用", min_length=1, max_length=32)
    is_default: bool = False


class CustomerAddressOut(BaseModel):
    id: int
    contact_name: str
    phone: str
    region: str
    detail: str
    tag: str
    is_default: bool
    created_at: str


class CustomerSearchHistoryOut(BaseModel):
    id: int
    keyword: str
    created_at: str


class CustomerSearchHistoryIn(BaseModel):
    keyword: str = Field(min_length=1, max_length=64)


class CustomerNotificationOut(BaseModel):
    id: int
    title: str
    summary: str
    kind: str
    route: str | None = None
    unread: bool
    created_at: str


class StorefrontMarqueeNoticeOut(BaseModel):
    id: int
    title: str
    body: str
    action_label: str
    action_type: str
    action_value: str | None = None
