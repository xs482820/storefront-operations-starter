from pydantic import BaseModel


class AutoCloseResultOut(BaseModel):
    cutoff_minutes: int
    scanned: int
    closed: int
    closed_order_nos: list[str]


class LowStockItemOut(BaseModel):
    sku_id: int
    sku_code: str
    sku_name: str
    product_name: str
    available_base_qty: int


class PaymentAnomalyOut(BaseModel):
    order_no: str
    order_status: str
    latest_payment_status: str | None = None
    latest_payment_no: str | None = None
    reason: str


class MaintenanceRunOut(BaseModel):
    auto_close: AutoCloseResultOut
    low_stock_count: int
    payment_anomaly_count: int


class PaymentReconcileResultOut(BaseModel):
    scanned: int
    fixed: int
    fixed_order_nos: list[str]


class PaymentTimeoutCompensateOut(BaseModel):
    cutoff_minutes: int
    scanned_orders: int
    canceled_orders: int
    failed_payments: int
    repaired_orders: int
    canceled_order_nos: list[str]
