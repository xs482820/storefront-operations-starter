"""add shipping proof fields to orders

Revision ID: 20260417_0008
Revises: 20260417_0007
Create Date: 2026-04-17 15:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260417_0008"
down_revision = "20260417_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("logistics_company", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("tracking_no", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_method", sa.String(length=32), nullable=True))
    op.add_column("orders", sa.Column("shipping_scene_images", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.add_column("orders", sa.Column("freight_payer", sa.String(length=32), nullable=True))
    op.add_column("orders", sa.Column("freight_paid_by_us", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("orders", sa.Column("freight_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("freight_payment_images", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.add_column("orders", sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_tracking_no", "orders", ["tracking_no"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_tracking_no", table_name="orders")
    op.drop_column("orders", "shipped_at")
    op.drop_column("orders", "freight_payment_images")
    op.drop_column("orders", "freight_amount")
    op.drop_column("orders", "freight_paid_by_us")
    op.drop_column("orders", "freight_payer")
    op.drop_column("orders", "shipping_scene_images")
    op.drop_column("orders", "shipping_method")
    op.drop_column("orders", "tracking_no")
    op.drop_column("orders", "logistics_company")
