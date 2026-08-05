from pydantic import BaseModel, Field

from app.models.enums import AfterSaleStatus, AfterSaleType


class AfterSaleCreateIn(BaseModel):
    order_no: str = Field(min_length=1, max_length=40)
    request_type: AfterSaleType
    requested_amount: str | None = Field(default=None)
    reason: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=255)


class AfterSaleStatusUpdateIn(BaseModel):
    status: AfterSaleStatus
    note: str | None = Field(default=None, max_length=255)


class AfterSaleOut(BaseModel):
    request_no: str
    order_no: str
    customer_id: int | None
    request_type: AfterSaleType
    status: AfterSaleStatus
    requested_amount: str | None = None
    reason: str
    note: str | None = None
    created_at: str
