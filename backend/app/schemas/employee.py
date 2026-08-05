from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AfterSaleProcessType, ShippingMode


class EmployeeShipOrderIn(BaseModel):
    shipping_mode: ShippingMode
    fulfillment_channel: str | None = Field(default=None, max_length=24)
    shipping_proof_url: str | None = Field(default=None, max_length=255)
    shipping_evidence: dict[str, list[str]] = Field(default_factory=dict)
    logistics_company: str | None = Field(default=None, max_length=64)
    carrier_contact: str | None = Field(default=None, max_length=64)
    tracking_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_fulfillment_details(self) -> "EmployeeShipOrderIn":
        channel = (self.fulfillment_channel or "").strip()
        if not channel:
            return self
        if channel not in {"courier", "linehaul", "local_delivery", "pickup"}:
            raise ValueError("unsupported fulfillment_channel")
        if channel == "courier":
            if self.shipping_mode != ShippingMode.EXPRESS:
                raise ValueError("courier fulfillment requires express shipping_mode")
            if not (self.logistics_company or "").strip() or not (self.tracking_no or "").strip():
                raise ValueError("courier fulfillment requires logistics_company and tracking_no")
        elif self.shipping_mode != ShippingMode.OFFLINE:
            raise ValueError("non-courier fulfillment requires offline shipping_mode")
        if channel == "linehaul" and not (self.logistics_company or "").strip():
            raise ValueError("linehaul fulfillment requires a carrier name")
        allowed_keys = {"handoff", "scene", "freight", "photos"}
        evidence = self.shipping_evidence or {}
        if set(evidence) - allowed_keys:
            raise ValueError("unsupported shipping evidence type")
        for urls in evidence.values():
            if not isinstance(urls, list) or len(urls) > 5 or any(not isinstance(url, str) or not url.strip() or len(url) > 255 for url in urls):
                raise ValueError("invalid shipping evidence")
        photos = evidence.get("photos")
        if photos is not None:
            minimum = {"courier": 1, "linehaul": 2, "local_delivery": 1, "pickup": 0}[channel]
            if len(photos) < minimum:
                raise ValueError("insufficient shipping photos")
            return self
        if channel == "courier" and not evidence.get("handoff"):
            raise ValueError("courier fulfillment requires handoff evidence")
        if channel == "linehaul" and (not evidence.get("scene") or not evidence.get("handoff")):
            raise ValueError("linehaul fulfillment requires scene and handoff evidence")
        if channel == "local_delivery" and not evidence.get("scene"):
            raise ValueError("local delivery requires scene evidence")
        return self


class EmployeeConfirmOfflinePaymentIn(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class EmployeeCancelOrderIn(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class EmployeeOrderNoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class EmployeeResolveAfterSaleIn(BaseModel):
    process_type: AfterSaleProcessType
    refund_amount: Decimal | None = Field(default=None, ge=0)
    chat_proof_url: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=255)
    customer_note: str | None = Field(default=None, max_length=255)
    internal_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_refund_amount(self) -> "EmployeeResolveAfterSaleIn":
        if self.process_type in {AfterSaleProcessType.REFUND_AND_RETURN, AfterSaleProcessType.REFUND_ONLY}:
            if self.refund_amount is None:
                raise ValueError("refund_amount is required for refund flows")
        return self


class EmployeeSetDeliverySignedIn(BaseModel):
    signed_at: datetime


class EmployeeImageGenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1500)
    reference_urls: list[str] = Field(default_factory=list, max_length=5)


class EmployeeImagePromptTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=1500)


class EmployeeQuickProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    product_code: str = Field(min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    image_urls: list[str] = Field(default_factory=list, max_length=5)
    retail_price: Decimal | None = Field(default=None, ge=0)
    wholesale_price: Decimal | None = Field(default=None, ge=0)
    min_wholesale_qty: int = Field(default=1, ge=1, le=9999)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_sale_price(self) -> "EmployeeQuickProductIn":
        if self.retail_price is None and self.wholesale_price is None:
            raise ValueError("at least one sale price is required")
        return self


class EmployeeWorkbenchSummaryOut(BaseModel):
    pending_payment_orders: int = 0
    awaiting_shipment_orders: int = 0
    shipped_orders: int = 0
    pending_aftersales: int = 0
    today_new_orders: int = 0
    today_new_aftersales: int = 0
