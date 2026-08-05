from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import PaymentStatus


class PaymentRecord(Base, TimestampMixin):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    openid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prepay_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    provider_txn_no: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
