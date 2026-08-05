"""add customer product favorites

Revision ID: 20260516_0021
Revises: 20260515_0020
Create Date: 2026-05-16 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260516_0021"
down_revision = "20260515_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_product_favorites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "product_id", name="uq_customer_favorite_user_product"),
    )
    op.create_index("ix_customer_product_favorites_user_id", "customer_product_favorites", ["user_id"])
    op.create_index("ix_customer_product_favorites_product_id", "customer_product_favorites", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_product_favorites_product_id", table_name="customer_product_favorites")
    op.drop_index("ix_customer_product_favorites_user_id", table_name="customer_product_favorites")
    op.drop_table("customer_product_favorites")
