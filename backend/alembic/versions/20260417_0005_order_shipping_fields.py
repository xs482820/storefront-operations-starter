"""order shipping fields

Revision ID: 20260417_0005
Revises: 20260417_0004
Create Date: 2026-04-17 21:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260417_0005"
down_revision = "20260417_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("shipping_fee", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("shipping_policy", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_province", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_city", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_district", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_address", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("shipping_recipient", sa.String(length=64), nullable=True))
    op.add_column("orders", sa.Column("shipping_phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "shipping_phone")
    op.drop_column("orders", "shipping_recipient")
    op.drop_column("orders", "shipping_address")
    op.drop_column("orders", "shipping_district")
    op.drop_column("orders", "shipping_city")
    op.drop_column("orders", "shipping_province")
    op.drop_column("orders", "shipping_policy")
    op.drop_column("orders", "shipping_fee")
