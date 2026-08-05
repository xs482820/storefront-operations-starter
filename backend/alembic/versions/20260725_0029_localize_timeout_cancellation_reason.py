"""localize historical timeout cancellation reason

Revision ID: 20260725_0029
Revises: 20260725_0028
Create Date: 2026-07-25 17:30:00
"""

from alembic import op


revision = "20260725_0029"
down_revision = "20260725_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE orders
        SET cancellation_reason = '超过支付时限，订单已自动取消'
        WHERE cancellation_source = 'auto_timeout'
          AND cancellation_reason = 'payment timeout'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE orders
        SET cancellation_reason = 'payment timeout'
        WHERE cancellation_source = 'auto_timeout'
          AND cancellation_reason = '超过支付时限，订单已自动取消'
        """
    )
