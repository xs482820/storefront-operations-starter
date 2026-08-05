from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_mixins import TimestampMixin
from app.models.enums import SKUType, StockChangeReason


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    product_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    spec_dim_1_name: Mapped[str] = mapped_column(String(32), nullable=False, default="颜色/形状", server_default="颜色/形状")
    spec_dim_2_name: Mapped[str] = mapped_column(String(32), nullable=False, default="尺码/大小", server_default="尺码/大小")
    supports_retail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    supports_wholesale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    has_dual_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    skus: Mapped[list["ProductSKU"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class ProductSKU(Base, TimestampMixin):
    __tablename__ = "product_skus"
    __table_args__ = (
        UniqueConstraint("product_id", "sku_type", "spec_value_1", "spec_value_2", name="uq_product_skus_product_type_specs"),
        CheckConstraint("online_stock >= 0", name="online_stock_non_negative"),
        CheckConstraint("retail_price >= 0", name="retail_price_non_negative"),
        CheckConstraint("wholesale_price >= 0", name="wholesale_price_non_negative"),
        CheckConstraint("min_sale_qty >= 1", name="min_sale_qty_positive"),
        CheckConstraint("min_wholesale_qty >= 1", name="min_wholesale_qty_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sku_type: Mapped[SKUType] = mapped_column(
        Enum(SKUType, name="sku_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    spec_value_1: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_value_2: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_mixed_pack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    mixed_pack_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    online_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    retail_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    wholesale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    min_sale_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    min_wholesale_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    product: Mapped["Product"] = relationship(back_populates="skus")
    stock_logs: Mapped[list["OnlineStockLog"]] = relationship(
        back_populates="sku",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OnlineStockLog(Base, TimestampMixin):
    __tablename__ = "online_stock_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False, index=True)
    delta_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    before_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    after_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[StockChangeReason] = mapped_column(
        Enum(StockChangeReason, name="stock_change_reason", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    ref_order_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    operator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sku: Mapped["ProductSKU"] = relationship(back_populates="stock_logs")
