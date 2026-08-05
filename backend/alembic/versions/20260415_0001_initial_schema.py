"""initial schema

Revision ID: 20260415_0001
Revises:
Create Date: 2026-04-15 01:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260415_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = sa.Enum("admin", "wholesale", "retail", name="user_role")
order_status = sa.Enum(
    "pending_payment",
    "paid",
    "picking",
    "shipped",
    "completed",
    "canceled",
    name="order_status",
)
stock_change_type = sa.Enum(
    "inbound",
    "outbound",
    "adjustment",
    "order_reserve",
    "order_release",
    "order_deduct",
    name="stock_change_type",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("brand", sa.String(length=64), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("product_code", name="uq_products_product_code"),
    )
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_brand", "products", ["brand"], unique=False)
    op.create_index("ix_products_product_code", "products", ["product_code"], unique=False)

    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("code", name="uq_units_code"),
    )

    op.create_table(
        "product_skus",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_code", sa.String(length=64), nullable=False),
        sa.Column("sku_name", sa.String(length=128), nullable=False),
        sa.Column("attrs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("retail_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("wholesale_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_wholesale_base_qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("retail_price >= 0", name="ck_product_skus_retail_price_non_negative"),
        sa.CheckConstraint("wholesale_price >= 0", name="ck_product_skus_wholesale_price_non_negative"),
        sa.UniqueConstraint("sku_code", name="uq_product_skus_sku_code"),
    )
    op.create_index("ix_product_skus_product_id", "product_skus", ["product_id"], unique=False)
    op.create_index("ix_product_skus_sku_code", "product_skus", ["sku_code"], unique=False)

    op.create_table(
        "sku_unit_conversions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_base_factor", sa.Integer(), nullable=False),
        sa.Column("is_base_unit", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint("to_base_factor > 0", name="ck_sku_unit_conversions_to_base_factor_positive"),
        sa.UniqueConstraint("sku_id", "unit_id", name="uq_sku_unit"),
    )
    op.create_index("ix_sku_unit_conversions_sku_id", "sku_unit_conversions", ["sku_id"], unique=False)

    op.create_table(
        "inventories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("on_hand_base_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_base_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("on_hand_base_qty >= 0", name="ck_inventories_on_hand_base_non_negative"),
        sa.CheckConstraint("reserved_base_qty >= 0", name="ck_inventories_reserved_base_non_negative"),
        sa.UniqueConstraint("sku_id", name="uq_inventory_sku"),
    )
    op.create_index("ix_inventories_sku_id", "inventories", ["sku_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", order_status, nullable=False, server_default="pending_payment"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payable_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("order_no", name="uq_orders_order_no"),
    )
    op.create_index("ix_orders_order_no", "orders", ["order_no"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("base_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_order_item_qty_positive"),
        sa.CheckConstraint("base_quantity > 0", name="ck_order_items_order_item_base_qty_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_items_order_item_unit_price_non_negative"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_items_sku_id", "order_items", ["sku_id"], unique=False)

    op.create_table(
        "stock_ledgers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("delta_base_qty", sa.Integer(), nullable=False),
        sa.Column("change_type", stock_change_type, nullable=False),
        sa.Column("ref_order_no", sa.String(length=40), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_stock_ledgers_sku_id", "stock_ledgers", ["sku_id"], unique=False)
    op.create_index("ix_stock_ledgers_ref_order_no", "stock_ledgers", ["ref_order_no"], unique=False)
    op.create_index("ix_stock_ledgers_change_type", "stock_ledgers", ["change_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_ledgers_change_type", table_name="stock_ledgers")
    op.drop_index("ix_stock_ledgers_ref_order_no", table_name="stock_ledgers")
    op.drop_index("ix_stock_ledgers_sku_id", table_name="stock_ledgers")
    op.drop_table("stock_ledgers")

    op.drop_index("ix_order_items_sku_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_order_no", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_inventories_sku_id", table_name="inventories")
    op.drop_table("inventories")

    op.drop_index("ix_sku_unit_conversions_sku_id", table_name="sku_unit_conversions")
    op.drop_table("sku_unit_conversions")

    op.drop_index("ix_product_skus_sku_code", table_name="product_skus")
    op.drop_index("ix_product_skus_product_id", table_name="product_skus")
    op.drop_table("product_skus")

    op.drop_table("units")

    op.drop_index("ix_products_product_code", table_name="products")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
