from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_mixins import TimestampMixin


class CustomerCartItem(Base, TimestampMixin):
    __tablename__ = "customer_cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "sku_id", name="uq_customer_cart_user_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class CustomerProductFavorite(Base, TimestampMixin):
    __tablename__ = "customer_product_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_customer_favorite_user_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)


class CustomerAddress(Base, TimestampMixin):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(32), nullable=False, default="常用", server_default="常用")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class CustomerSearchHistory(Base, TimestampMixin):
    __tablename__ = "customer_search_histories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class CustomerNotification(Base, TimestampMixin):
    __tablename__ = "customer_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="system", server_default="system")
    route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unread: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
