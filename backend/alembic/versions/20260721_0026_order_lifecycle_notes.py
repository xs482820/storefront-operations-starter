"""separate customer and internal order lifecycle notes

Revision ID: 20260721_0026
Revises: 20260721_0025
Create Date: 2026-07-21 13:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0026"
down_revision = "20260721_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("customer_note", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("internal_note", sa.String(length=1000), nullable=True))
    op.add_column("orders", sa.Column("termination_reason", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("termination_disposition", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("terminated_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_orders_terminated_by_user", "orders", "users", ["terminated_by_user_id"], ["id"], ondelete="SET NULL")
    op.add_column("aftersale_requests", sa.Column("customer_note", sa.String(length=255), nullable=True))
    op.add_column("aftersale_requests", sa.Column("internal_note", sa.String(length=1000), nullable=True))
    op.execute("UPDATE orders SET customer_note = note WHERE customer_note IS NULL AND note IS NOT NULL")
    op.execute("UPDATE aftersale_requests SET customer_note = note WHERE customer_note IS NULL AND note IS NOT NULL")


def downgrade() -> None:
    op.drop_column("aftersale_requests", "internal_note")
    op.drop_column("aftersale_requests", "customer_note")
    op.drop_constraint("fk_orders_terminated_by_user", "orders", type_="foreignkey")
    op.drop_column("orders", "terminated_by_user_id")
    op.drop_column("orders", "terminated_at")
    op.drop_column("orders", "termination_disposition")
    op.drop_column("orders", "termination_reason")
    op.drop_column("orders", "internal_note")
    op.drop_column("orders", "customer_note")
