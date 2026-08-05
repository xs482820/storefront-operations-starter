from decimal import Decimal

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import AfterSaleProcessType, AfterSaleReason, AfterSaleStatus


class AfterSaleRequest(Base, TimestampMixin):
    __tablename__ = "aftersale_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reason: Mapped[AfterSaleReason] = mapped_column(
        Enum(AfterSaleReason, name="aftersale_reason", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    custom_reason_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    process_type: Mapped[AfterSaleProcessType | None] = mapped_column(
        Enum(AfterSaleProcessType, name="aftersale_process_type", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    handler_employee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    chat_proof_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[AfterSaleStatus] = mapped_column(
        Enum(AfterSaleStatus, name="aftersale_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AfterSaleStatus.PENDING,
        server_default=AfterSaleStatus.PENDING.value,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
