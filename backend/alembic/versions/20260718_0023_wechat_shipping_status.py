"""track wechat shipping upload status

Revision ID: 20260718_0023
Revises: 20260705_0022
Create Date: 2026-07-18 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718_0023"
down_revision = "20260705_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("wechat_shipping_status", sa.String(length=16), nullable=True))
    op.add_column("orders", sa.Column("wechat_shipping_error", sa.String(length=512), nullable=True))
    op.add_column("orders", sa.Column("wechat_shipping_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("wechat_shipping_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("wechat_shipping_uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_wechat_shipping_status", "orders", ["wechat_shipping_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_wechat_shipping_status", table_name="orders")
    op.drop_column("orders", "wechat_shipping_uploaded_at")
    op.drop_column("orders", "wechat_shipping_attempted_at")
    op.drop_column("orders", "wechat_shipping_attempts")
    op.drop_column("orders", "wechat_shipping_error")
    op.drop_column("orders", "wechat_shipping_status")
