from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import StockChangeType, StockDocumentStatus, StockDocumentType


class StockDocument(Base, TimestampMixin):
    __tablename__ = "stock_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    doc_type: Mapped[StockDocumentType] = mapped_column(
        Enum(
            StockDocumentType,
            name="stock_document_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[StockDocumentStatus] = mapped_column(
        Enum(
            StockDocumentStatus,
            name="stock_document_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=StockDocumentStatus.APPLIED,
        server_default=StockDocumentStatus.APPLIED.value,
        index=True,
    )
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_base_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    items: Mapped[list["StockDocumentItem"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class StockDocumentItem(Base):
    __tablename__ = "stock_document_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("stock_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[int] = mapped_column(
        ForeignKey("product_skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta_base_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped["StockDocument"] = relationship(back_populates="items")


class StockLedger(Base, TimestampMixin):
    __tablename__ = "stock_ledgers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(
        ForeignKey("product_skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    delta_base_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[StockChangeType] = mapped_column(
        Enum(
            StockChangeType,
            name="stock_change_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    ref_order_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
