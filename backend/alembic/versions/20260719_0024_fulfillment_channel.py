"""record actual fulfillment channel

Revision ID: 20260719_0024
Revises: 20260718_0023
Create Date: 2026-07-19 01:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_0024"
down_revision = "20260718_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("fulfillment_channel", sa.String(length=24), nullable=True))
    op.add_column("orders", sa.Column("carrier_contact", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "carrier_contact")
    op.drop_column("orders", "fulfillment_channel")
