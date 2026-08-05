from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import OrderStatus, PaymentMethod, ShippingMode, UserRole


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    buyer_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="order_buyer_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OrderStatus.PENDING_PAYMENT,
        server_default=OrderStatus.PENDING_PAYMENT.value,
        index=True,
    )
    original_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PaymentMethod.WECHAT_PAY,
        server_default=PaymentMethod.WECHAT_PAY.value,
        index=True,
    )
    shipping_mode: Mapped[ShippingMode | None] = mapped_column(
        Enum(ShippingMode, name="shipping_mode", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )
    shipping_proof_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_evidence: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    logistics_company: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfillment_channel: Mapped[str | None] = mapped_column(String(24), nullable=True)
    carrier_contact: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    wechat_shipping_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    wechat_shipping_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wechat_shipping_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    wechat_shipping_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wechat_shipping_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipping_recipient: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shipping_province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    termination_disposition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancellation_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    sku_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_type_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    spec_value_1_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_value_2_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
