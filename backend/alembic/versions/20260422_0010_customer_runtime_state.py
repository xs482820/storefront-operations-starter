"""add customer runtime state tables

Revision ID: 20260422_0010
Revises: 20260417_0009
Create Date: 2026-04-22 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260422_0010"
down_revision = "20260417_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_profiles", sa.Column("avatar_url", sa.String(length=255), nullable=True))
    op.add_column("customer_profiles", sa.Column("wechat_openid", sa.String(length=64), nullable=True))
    op.add_column("customer_profiles", sa.Column("wechat_unionid", sa.String(length=64), nullable=True))
    op.create_index("ix_customer_profiles_wechat_openid", "customer_profiles", ["wechat_openid"], unique=True)
    op.create_index("ix_customer_profiles_wechat_unionid", "customer_profiles", ["wechat_unionid"], unique=True)

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("district", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_addresses")),
    )
    op.create_index(op.f("ix_customer_addresses_user_id"), "customer_addresses", ["user_id"], unique=False)

    op.create_table(
        "shopping_cart_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("unit_code", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["sku_id"], ["product_skus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_cart_items")),
        sa.UniqueConstraint("user_id", "sku_id", "unit_code", name="uq_cart_user_sku_unit"),
    )
    op.create_index(op.f("ix_shopping_cart_items_sku_id"), "shopping_cart_items", ["sku_id"], unique=False)
    op.create_index(op.f("ix_shopping_cart_items_user_id"), "shopping_cart_items", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shopping_cart_items_user_id"), table_name="shopping_cart_items")
    op.drop_index(op.f("ix_shopping_cart_items_sku_id"), table_name="shopping_cart_items")
    op.drop_table("shopping_cart_items")

    op.drop_index(op.f("ix_customer_addresses_user_id"), table_name="customer_addresses")
    op.drop_table("customer_addresses")

    op.drop_index("ix_customer_profiles_wechat_unionid", table_name="customer_profiles")
    op.drop_index("ix_customer_profiles_wechat_openid", table_name="customer_profiles")
    op.drop_column("customer_profiles", "wechat_unionid")
    op.drop_column("customer_profiles", "wechat_openid")
    op.drop_column("customer_profiles", "avatar_url")
