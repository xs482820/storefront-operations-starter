"""refactor business core schema

Revision ID: 20260424_0012
Revises: 20260423_0011
Create Date: 2026-04-24 01:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260424_0012"
down_revision = "20260423_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Major refactor: the old unified inventory/order schema is intentionally
    # replaced with a lighter online-stock-first structure.
    for table in [
        "system_logs",
        "aftersale_requests",
        "payment_records",
        "order_items",
        "orders",
        "online_stock_logs",
        "inventories",
        "stock_document_items",
        "stock_documents",
        "stock_ledgers",
        "sku_unit_conversions",
        "units",
        "product_skus",
        "product_categories",
        "products",
        "shopping_cart_items",
        "customer_addresses",
        "wholesale_applications",
        "customer_profiles",
        "users",
    ]:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    for type_name in [
        "system_log_category",
        "stock_change_reason",
        "aftersale_process_type",
        "aftersale_reason",
        "aftersale_status",
        "payment_method",
        "shipping_mode",
        "payment_status",
        "order_status",
        "order_buyer_role",
        "sku_type",
        "wholesale_application_status",
        "user_role",
        "stock_change_type",
        "stock_document_type",
        "stock_document_status",
        "aftersale_type",
    ]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {type_name} CASCADE"))

    user_role = postgresql.ENUM("admin", "employee", "retail", "wholesale", name="user_role", create_type=False)
    wholesale_application_status = postgresql.ENUM("pending", "approved", "rejected", name="wholesale_application_status", create_type=False)
    sku_type = postgresql.ENUM("retail", "wholesale", name="sku_type", create_type=False)
    order_buyer_role = postgresql.ENUM("admin", "employee", "retail", "wholesale", name="order_buyer_role", create_type=False)
    order_status = postgresql.ENUM("pending_payment", "awaiting_shipment", "shipped", "completed", "canceled", name="order_status", create_type=False)
    payment_method = postgresql.ENUM("wechat_pay", "offline_transfer", name="payment_method", create_type=False)
    payment_status = postgresql.ENUM("pending", "paid", "failed", "refunded", name="payment_status", create_type=False)
    shipping_mode = postgresql.ENUM("express", "offline", name="shipping_mode", create_type=False)
    aftersale_reason = postgresql.ENUM("quality_issue", "wrong_item", "damaged", "size_problem", "other", name="aftersale_reason", create_type=False)
    aftersale_process_type = postgresql.ENUM("refund_and_return", "refund_only", "exchange", "rejected", name="aftersale_process_type", create_type=False)
    aftersale_status = postgresql.ENUM("pending", "resolved", name="aftersale_status", create_type=False)
    stock_change_reason = postgresql.ENUM("admin_set", "admin_adjust", "order_create", "order_cancel", "manual_restore", name="stock_change_reason", create_type=False)
    system_log_category = postgresql.ENUM("order", "payment", "aftersale", "stock", "scheduler", name="system_log_category", create_type=False)

    bind = op.get_bind()
    for enum_obj in [
        user_role,
        wholesale_application_status,
        sku_type,
        order_buyer_role,
        order_status,
        payment_method,
        payment_status,
        shipping_mode,
        aftersale_reason,
        aftersale_process_type,
        aftersale_status,
        stock_change_reason,
        system_log_category,
    ]:
        enum_obj.create(bind, checkfirst=True)

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
        "customer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("avatar_url", sa.String(length=255), nullable=True),
        sa.Column("wechat_openid", sa.String(length=64), nullable=True),
        sa.Column("wechat_unionid", sa.String(length=64), nullable=True),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("store_name", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("business_license_url", sa.String(length=255), nullable=True),
        sa.Column("is_verified_wholesale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_customer_profiles_user_id"),
        sa.UniqueConstraint("phone", name="uq_customer_profiles_phone"),
        sa.UniqueConstraint("wechat_openid", name="uq_customer_profiles_wechat_openid"),
        sa.UniqueConstraint("wechat_unionid", name="uq_customer_profiles_wechat_unionid"),
    )
    op.create_index("ix_customer_profiles_user_id", "customer_profiles", ["user_id"], unique=False)
    op.create_index("ix_customer_profiles_phone", "customer_profiles", ["phone"], unique=False)
    op.create_index("ix_customer_profiles_wechat_openid", "customer_profiles", ["wechat_openid"], unique=False)

    op.create_table(
        "wholesale_applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", wholesale_application_status, nullable=False, server_default="pending"),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("store_name", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("business_license_url", sa.String(length=255), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("review_note", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_wholesale_applications_user_id", "wholesale_applications", ["user_id"], unique=False)
    op.create_index("ix_wholesale_applications_status", "wholesale_applications", ["status"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("brand", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spec_dim_1_name", sa.String(length=32), nullable=False, server_default="颜色/形状"),
        sa.Column("spec_dim_2_name", sa.String(length=32), nullable=False, server_default="尺码/大小"),
        sa.Column("supports_retail", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("supports_wholesale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_dual_price", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("product_code", name="uq_products_product_code"),
    )
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_model_name", "products", ["model_name"], unique=False)
    op.create_index("ix_products_product_code", "products", ["product_code"], unique=False)

    op.create_table(
        "product_skus",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_code", sa.String(length=64), nullable=False),
        sa.Column("sku_type", sku_type, nullable=False),
        sa.Column("spec_value_1", sa.String(length=64), nullable=True),
        sa.Column("spec_value_2", sa.String(length=64), nullable=True),
        sa.Column("sku_label", sa.String(length=128), nullable=True),
        sa.Column("is_mixed_pack", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mixed_pack_note", sa.String(length=255), nullable=True),
        sa.Column("online_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retail_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("wholesale_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("min_sale_qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_wholesale_qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("online_stock >= 0", name="ck_product_skus_online_stock_non_negative"),
        sa.CheckConstraint("retail_price >= 0", name="ck_product_skus_retail_price_non_negative"),
        sa.CheckConstraint("wholesale_price >= 0", name="ck_product_skus_wholesale_price_non_negative"),
        sa.CheckConstraint("min_sale_qty >= 1", name="ck_product_skus_min_sale_qty_positive"),
        sa.CheckConstraint("min_wholesale_qty >= 1", name="ck_product_skus_min_wholesale_qty_positive"),
        sa.UniqueConstraint("sku_code", name="uq_product_skus_sku_code"),
        sa.UniqueConstraint("product_id", "sku_type", "spec_value_1", "spec_value_2", name="uq_product_skus_product_type_specs"),
    )
    op.create_index("ix_product_skus_product_id", "product_skus", ["product_id"], unique=False)
    op.create_index("ix_product_skus_sku_code", "product_skus", ["sku_code"], unique=False)
    op.create_index("ix_product_skus_sku_type", "product_skus", ["sku_type"], unique=False)

    op.create_table(
        "online_stock_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("before_qty", sa.Integer(), nullable=False),
        sa.Column("after_qty", sa.Integer(), nullable=False),
        sa.Column("reason", stock_change_reason, nullable=False),
        sa.Column("ref_order_no", sa.String(length=40), nullable=True),
        sa.Column("operator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_online_stock_logs_sku_id", "online_stock_logs", ["sku_id"], unique=False)
    op.create_index("ix_online_stock_logs_reason", "online_stock_logs", ["reason"], unique=False)
    op.create_index("ix_online_stock_logs_ref_order_no", "online_stock_logs", ["ref_order_no"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("buyer_role", order_buyer_role, nullable=False),
        sa.Column("status", order_status, nullable=False, server_default="pending_payment"),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shipping_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payable_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_method", payment_method, nullable=False, server_default="wechat_pay"),
        sa.Column("shipping_mode", shipping_mode, nullable=True),
        sa.Column("shipping_proof_url", sa.String(length=255), nullable=True),
        sa.Column("logistics_company", sa.String(length=64), nullable=True),
        sa.Column("tracking_no", sa.String(length=64), nullable=True),
        sa.Column("shipping_recipient", sa.String(length=64), nullable=True),
        sa.Column("shipping_phone", sa.String(length=32), nullable=True),
        sa.Column("shipping_province", sa.String(length=64), nullable=True),
        sa.Column("shipping_city", sa.String(length=64), nullable=True),
        sa.Column("shipping_district", sa.String(length=64), nullable=True),
        sa.Column("shipping_address", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("order_no", name="uq_orders_order_no"),
    )
    op.create_index("ix_orders_order_no", "orders", ["order_no"], unique=False)
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_payment_method", "orders", ["payment_method"], unique=False)
    op.create_index("ix_orders_shipping_mode", "orders", ["shipping_mode"], unique=False)
    op.create_index("ix_orders_tracking_no", "orders", ["tracking_no"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("sku_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("sku_type_snapshot", sa.String(length=16), nullable=False),
        sa.Column("spec_value_1_snapshot", sa.String(length=64), nullable=True),
        sa.Column("spec_value_2_snapshot", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_items_sku_id", "order_items", ["sku_id"], unique=False)

    op.create_table(
        "payment_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payment_no", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", payment_status, nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=True),
        sa.Column("prepay_id", sa.String(length=80), nullable=True),
        sa.Column("provider_txn_no", sa.String(length=80), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("payment_no", name="uq_payment_records_payment_no"),
    )
    op.create_index("ix_payment_records_payment_no", "payment_records", ["payment_no"], unique=False)
    op.create_index("ix_payment_records_order_id", "payment_records", ["order_id"], unique=False)
    op.create_index("ix_payment_records_status", "payment_records", ["status"], unique=False)
    op.create_index("ix_payment_records_prepay_id", "payment_records", ["prepay_id"], unique=False)
    op.create_index("ix_payment_records_provider_txn_no", "payment_records", ["provider_txn_no"], unique=False)

    op.create_table(
        "aftersale_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", aftersale_reason, nullable=False),
        sa.Column("custom_reason_text", sa.String(length=255), nullable=True),
        sa.Column("process_type", aftersale_process_type, nullable=True),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("handler_employee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chat_proof_url", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("status", aftersale_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_aftersale_requests_order_id", "aftersale_requests", ["order_id"], unique=False)
    op.create_index("ix_aftersale_requests_customer_id", "aftersale_requests", ["customer_id"], unique=False)
    op.create_index("ix_aftersale_requests_reason", "aftersale_requests", ["reason"], unique=False)
    op.create_index("ix_aftersale_requests_status", "aftersale_requests", ["status"], unique=False)

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", system_log_category, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("order_no", sa.String(length=40), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_system_logs_category", "system_logs", ["category"], unique=False)
    op.create_index("ix_system_logs_action", "system_logs", ["action"], unique=False)
    op.create_index("ix_system_logs_order_no", "system_logs", ["order_no"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for the refactor migration")
