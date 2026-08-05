"""add product image urls field

Revision ID: 20260425_0014
Revises: 20260424_0013
Create Date: 2026-04-25 10:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260425_0014"
down_revision = "20260424_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("image_urls", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("products", "image_urls")
