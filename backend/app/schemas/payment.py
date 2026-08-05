from pydantic import BaseModel, Field

from app.models.enums import PaymentStatus


class PaymentCreateIn(BaseModel):
    order_no: str = Field(min_length=1, max_length=40)
    channel: str = Field(default="wechat_jsapi", max_length=32)
    openid: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=255)


class PaymentCreateOut(BaseModel):
    payment_no: str
    order_no: str
    channel: str
    status: PaymentStatus
    amount: str
    prepay_id: str | None = None
    code_url: str | None = None
    jsapi_params: dict | None = None
    message: str


class PaymentRecordOut(BaseModel):
    payment_no: str
    order_no: str
    channel: str
    status: PaymentStatus
    amount: str
    openid: str | None = None
    prepay_id: str | None = None
    provider_txn_no: str | None = None
    note: str | None = None
    created_at: str


class PaymentStatusUpdateIn(BaseModel):
    status: PaymentStatus
    provider_txn_no: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=255)


class PaymentSyncIn(BaseModel):
    order_id: int


class PaymentRefundIn(BaseModel):
    order_no: str = Field(min_length=1, max_length=40)
    refund_amount: str | None = Field(default=None, description="为空时默认全额退款")
    reason: str | None = Field(default=None, max_length=255)


class PaymentRefundOut(BaseModel):
    order_no: str
    payment_no: str
    status: PaymentStatus
    refund_no: str
    refund_amount: str
    message: str
