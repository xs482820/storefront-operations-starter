import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"
    RETAIL = "retail"
    WHOLESALE = "wholesale"


class WholesaleApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SKUType(str, enum.Enum):
    RETAIL = "retail"
    WHOLESALE = "wholesale"


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    AWAITING_SHIPMENT = "awaiting_shipment"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELED = "canceled"
    DELETED = "deleted"


class PaymentMethod(str, enum.Enum):
    WECHAT_PAY = "wechat_pay"
    OFFLINE_TRANSFER = "offline_transfer"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class ShippingMode(str, enum.Enum):
    EXPRESS = "express"
    OFFLINE = "offline"


class AfterSaleReason(str, enum.Enum):
    QUALITY_ISSUE = "quality_issue"
    WRONG_ITEM = "wrong_item"
    DAMAGED = "damaged"
    SIZE_PROBLEM = "size_problem"
    OTHER = "other"


class AfterSaleProcessType(str, enum.Enum):
    REFUND_AND_RETURN = "refund_and_return"
    REFUND_ONLY = "refund_only"
    EXCHANGE = "exchange"
    REJECTED = "rejected"


class AfterSaleStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"


class StockChangeReason(str, enum.Enum):
    ADMIN_SET = "admin_set"
    ADMIN_ADJUST = "admin_adjust"
    ORDER_CREATE = "order_create"
    ORDER_CANCEL = "order_cancel"
    MANUAL_RESTORE = "manual_restore"


class SystemLogCategory(str, enum.Enum):
    ORDER = "order"
    PAYMENT = "payment"
    AFTERSALE = "aftersale"
    STOCK = "stock"
    SCHEDULER = "scheduler"
