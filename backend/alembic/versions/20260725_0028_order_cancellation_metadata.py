"""add order cancellation metadata

Revision ID: 20260725_0028
Revises: 20260721_0027
Create Date: 2026-07-25 12:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260725_0028"
down_revision: str | None = "20260721_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("cancellation_reason", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("cancellation_source", sa.String(length=32), nullable=True))
    op.execute(
        """
        UPDATE orders AS o
        SET cancellation_source = 'auto_timeout',
            cancellation_reason = '超过支付时限，订单已自动取消'
        WHERE o.status = 'canceled'
          AND o.terminated_at IS NULL
          AND EXISTS (
              SELECT 1
              FROM business_events AS e
              WHERE e.entity_type = 'order'
                AND e.entity_id = o.id
                AND e.action_code = 'order.canceled'
                AND e.source = 'system'
          )
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "cancellation_source")
    op.drop_column("orders", "cancellation_reason")
