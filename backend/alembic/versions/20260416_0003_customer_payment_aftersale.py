"""customer payment aftersale

Revision ID: 20260416_0003
Revises: 20260416_0002
Create Date: 2026-04-16 17:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0003"
down_revision = "20260416_0002"
branch_labels = None
depends_on = None


payment_status = sa.Enum("pending", "paid", "failed", "refunded", name="payment_status")
aftersale_type = sa.Enum("refund", "return", "exchange", name="aftersale_type")
aftersale_status = sa.Enum("pending", "approved", "rejected", "completed", name="aftersale_status")


def upgrade() -> None:
    op.add_column("orders", sa.Column("note", sa.String(length=255), nullable=True))

    op.create_table(
        "customer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("is_verified_wholesale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_customer_profiles_user_id"),
    )
    op.create_index("ix_customer_profiles_user_id", "customer_profiles", ["user_id"], unique=False)
    op.create_index("ix_customer_profiles_phone", "customer_profiles", ["phone"], unique=False)

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
        sa.Column("request_no", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_type", aftersale_type, nullable=False),
        sa.Column("status", aftersale_status, nullable=False, server_default="pending"),
        sa.Column("requested_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("request_no", name="uq_aftersale_requests_request_no"),
    )
    op.create_index("ix_aftersale_requests_request_no", "aftersale_requests", ["request_no"], unique=False)
    op.create_index("ix_aftersale_requests_order_id", "aftersale_requests", ["order_id"], unique=False)
    op.create_index("ix_aftersale_requests_customer_id", "aftersale_requests", ["customer_id"], unique=False)
    op.create_index("ix_aftersale_requests_request_type", "aftersale_requests", ["request_type"], unique=False)
    op.create_index("ix_aftersale_requests_status", "aftersale_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_aftersale_requests_status", table_name="aftersale_requests")
    op.drop_index("ix_aftersale_requests_request_type", table_name="aftersale_requests")
    op.drop_index("ix_aftersale_requests_customer_id", table_name="aftersale_requests")
    op.drop_index("ix_aftersale_requests_order_id", table_name="aftersale_requests")
    op.drop_index("ix_aftersale_requests_request_no", table_name="aftersale_requests")
    op.drop_table("aftersale_requests")

    op.drop_index("ix_payment_records_provider_txn_no", table_name="payment_records")
    op.drop_index("ix_payment_records_prepay_id", table_name="payment_records")
    op.drop_index("ix_payment_records_status", table_name="payment_records")
    op.drop_index("ix_payment_records_order_id", table_name="payment_records")
    op.drop_index("ix_payment_records_payment_no", table_name="payment_records")
    op.drop_table("payment_records")

    op.drop_index("ix_customer_profiles_phone", table_name="customer_profiles")
    op.drop_index("ix_customer_profiles_user_id", table_name="customer_profiles")
    op.drop_table("customer_profiles")

    op.drop_column("orders", "note")
