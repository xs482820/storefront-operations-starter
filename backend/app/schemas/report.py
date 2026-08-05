from decimal import Decimal

from pydantic import BaseModel


class SalesRoleBreakdownOut(BaseModel):
    role: str
    orders: int
    paid_orders: int
    paid_amount: Decimal


class SalesSummaryOut(BaseModel):
    from_date: str
    to_date: str
    total_orders: int
    paid_orders: int
    canceled_orders: int
    paid_amount: Decimal
    by_role: list[SalesRoleBreakdownOut]
