"""add product categories catalog

Revision ID: 20260424_0013
Revises: 20260424_0012
Create Date: 2026-04-24 20:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0013"
down_revision = "20260424_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_product_categories_name"),
    )
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.drop_table("product_categories")
