"""add order soft delete fields and deleted status

Revision ID: 20260515_0020
Revises: 20260512_0019
Create Date: 2026-05-15 20:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260515_0020"
down_revision = "20260512_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "orders",
        sa.Column("deleted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    bind = op.get_bind()
    order_status = postgresql.ENUM(
        "pending_payment",
        "awaiting_shipment",
        "shipped",
        "completed",
        "canceled",
        "deleted",
        name="order_status",
        create_type=False,
    )
    order_status.create(bind, checkfirst=True)
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'deleted'")

    op.create_index("ix_orders_deleted_at", "orders", ["deleted_at"], unique=False)
    op.create_index("ix_orders_deleted_by_user_id", "orders", ["deleted_by_user_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for the order soft delete migration")
