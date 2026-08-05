from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import OrderStatus


class OrderCreateItemIn(BaseModel):
    sku_id: int
    unit_code: str = Field(min_length=1, max_length=32)
    quantity: int = Field(gt=0)


class OrderCreateIn(BaseModel):
    items: list[OrderCreateItemIn]
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    customer_id: int | None = None
    shipping_province: str | None = Field(default=None, max_length=64)
    shipping_city: str | None = Field(default=None, max_length=64)
    shipping_district: str | None = Field(default=None, max_length=64)
    shipping_address: str | None = Field(default=None, max_length=255)
    shipping_recipient: str | None = Field(default=None, max_length=64)
    shipping_phone: str | None = Field(default=None, max_length=32)
    shipping_fee_override: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=255)


class OrderCreateOut(BaseModel):
    order_no: str
    status: OrderStatus
    total_amount: Decimal
    discount_amount: Decimal
    shipping_fee: Decimal
    shipping_policy: str | None = None
    payable_amount: Decimal


class OrderStatusUpdateIn(BaseModel):
    status: OrderStatus


class OrderShipConfirmIn(BaseModel):
    logistics_company: str | None = Field(default=None, max_length=64)
    tracking_no: str | None = Field(default=None, max_length=64)
    shipping_method: str = Field(default="logistics", max_length=32)
    shipping_scene_images: list[str] = Field(default_factory=list, max_length=3)
    freight_payer: str = Field(default="customer", max_length=32)
    freight_paid_by_us: bool = False
    freight_amount: Decimal | None = Field(default=None, ge=0)
    freight_payment_images: list[str] = Field(default_factory=list, max_length=3)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("shipping_scene_images", "freight_payment_images")
    @classmethod
    def validate_images(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(value):
            raise ValueError("image url cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_freight(self) -> "OrderShipConfirmIn":
        if self.freight_paid_by_us:
            if self.freight_amount is None:
                raise ValueError("freight_amount is required when freight_paid_by_us is true")
            if not self.freight_payment_images:
                raise ValueError("freight_payment_images is required when freight_paid_by_us is true")
        return self


class OrderItemOut(BaseModel):
    sku_id: int
    unit_id: int
    product_name: str | None = None
    sku_name: str | None = None
    sku_code: str | None = None
    unit_code: str | None = None
    unit_name: str | None = None
    quantity: int
    base_quantity: int
    unit_price: str
    line_amount: str


class OrderDetailOut(BaseModel):
    order_no: str
    customer_id: int | None
    status: OrderStatus
    total_amount: str
    discount_amount: str
    shipping_fee: str
    shipping_policy: str | None = None
    shipping_province: str | None = None
    shipping_city: str | None = None
    shipping_district: str | None = None
    shipping_address: str | None = None
    shipping_recipient: str | None = None
    shipping_phone: str | None = None
    logistics_company: str | None = None
    tracking_no: str | None = None
    shipping_method: str | None = None
    shipping_scene_images: list[str] = []
    freight_payer: str | None = None
    freight_paid_by_us: bool = False
    freight_amount: str | None = None
    freight_payment_images: list[str] = []
    shipped_at: str | None = None
    payable_amount: str
    created_at: str
    items: list[OrderItemOut]


class ShippingQuoteIn(BaseModel):
    customer_id: int | None = None
    merchandise_amount: Decimal = Field(ge=0)
    shipping_province: str | None = Field(default=None, max_length=64)
    shipping_city: str | None = Field(default=None, max_length=64)


class ShippingQuoteOut(BaseModel):
    shipping_fee: Decimal
    shipping_policy: str


class OrderAutoCloseOut(BaseModel):
    cutoff_minutes: int
    scanned: int
    closed: int
    closed_order_nos: list[str]
