"""add customer runtime storage tables

Revision ID: 20260507_0016
Revises: 20260425_0015
Create Date: 2026-05-07 14:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0016"
down_revision = "20260425_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "sku_id", name="uq_customer_cart_user_sku"),
    )
    op.create_index("ix_customer_cart_items_user_id", "customer_cart_items", ["user_id"])
    op.create_index("ix_customer_cart_items_sku_id", "customer_cart_items", ["sku_id"])

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=False),
        sa.Column("tag", sa.String(length=32), nullable=False, server_default="常用"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_customer_addresses_user_id", "customer_addresses", ["user_id"])

    op.create_table(
        "customer_search_histories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_customer_search_histories_user_id", "customer_search_histories", ["user_id"])
    op.create_index("ix_customer_search_histories_keyword", "customer_search_histories", ["keyword"])

    op.create_table(
        "customer_notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("unread", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_customer_notifications_user_id", "customer_notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_notifications_user_id", table_name="customer_notifications")
    op.drop_table("customer_notifications")

    op.drop_index("ix_customer_search_histories_keyword", table_name="customer_search_histories")
    op.drop_index("ix_customer_search_histories_user_id", table_name="customer_search_histories")
    op.drop_table("customer_search_histories")

    op.drop_index("ix_customer_addresses_user_id", table_name="customer_addresses")
    op.drop_table("customer_addresses")

    op.drop_index("ix_customer_cart_items_sku_id", table_name="customer_cart_items")
    op.drop_index("ix_customer_cart_items_user_id", table_name="customer_cart_items")
    op.drop_table("customer_cart_items")
