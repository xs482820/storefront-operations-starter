"""add employee_mode to customer_profiles

Revision ID: 20260510_0017
Revises: 20260507_0016
Create Date: 2026-05-10 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0017"
down_revision = "20260507_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_profiles",
        sa.Column("employee_mode", sa.String(length=16), nullable=False, server_default="shopping"),
    )


def downgrade() -> None:
    op.drop_column("customer_profiles", "employee_mode")

