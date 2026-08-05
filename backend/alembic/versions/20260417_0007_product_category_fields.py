"""add product category fields

Revision ID: 20260417_0007
Revises: 20260417_0006
Create Date: 2026-04-17 14:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260417_0007"
down_revision = "20260417_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("subcategory", sa.String(length=64), nullable=True))
    op.create_index("ix_products_category", "products", ["category"], unique=False)
    op.create_index("ix_products_subcategory", "products", ["subcategory"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_subcategory", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_column("products", "subcategory")
    op.drop_column("products", "category")
