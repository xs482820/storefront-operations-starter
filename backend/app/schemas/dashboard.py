from decimal import Decimal

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    total_products: int
    total_skus: int
    total_users: int
    total_orders: int
    total_stock_documents: int
    total_payments: int
    total_aftersales: int
    pending_orders: int
    paid_orders: int
    low_stock_skus: int
    total_inventory_base_qty: int
    total_inventory_value: Decimal


class DashboardSalesPointOut(BaseModel):
    date: str
    orders: int
    paid_orders: int
    paid_amount: Decimal


class DashboardSalesOverviewOut(BaseModel):
    from_date: str
    to_date: str
    total_orders: int
    total_paid_orders: int
    total_paid_amount: Decimal
    total_canceled_orders: int
    points: list[DashboardSalesPointOut]
