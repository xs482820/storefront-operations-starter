"""add employee role and managed product categories

Revision ID: 20260423_0011
Revises: 20260422_0010
Create Date: 2026-04-23 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_0011"
down_revision = "20260422_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'employee'")

    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("parent_id", "name", name="uq_product_categories_parent_name"),
        sa.UniqueConstraint("code", name="uq_product_categories_code"),
    )
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"], unique=False)
    op.create_index("ix_product_categories_name", "product_categories", ["name"], unique=False)
    op.create_index("ix_product_categories_code", "product_categories", ["code"], unique=False)

    op.execute(
        """
        INSERT INTO product_categories (name, code, sort_order, is_active)
        SELECT DISTINCT category, lower(regexp_replace(category, '[^a-zA-Z0-9]+', '-', 'g')), 0, true
        FROM products
        WHERE category IS NOT NULL AND category <> ''
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO product_categories (parent_id, name, code, sort_order, is_active)
        SELECT pc.id, distinct_sub.subcategory,
               lower(regexp_replace(coalesce(distinct_sub.category, 'root') || '-' || distinct_sub.subcategory, '[^a-zA-Z0-9]+', '-', 'g')),
               0,
               true
        FROM (
            SELECT DISTINCT category, subcategory
            FROM products
            WHERE category IS NOT NULL AND category <> '' AND subcategory IS NOT NULL AND subcategory <> ''
        ) AS distinct_sub
        JOIN product_categories pc
          ON pc.parent_id IS NULL
         AND pc.name = distinct_sub.category
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_product_categories_code", table_name="product_categories")
    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.drop_index("ix_product_categories_parent_id", table_name="product_categories")
    op.drop_table("product_categories")
