"""add logical deletion fields for internal accounts and aftersales

Revision ID: 20260721_0025
Revises: 20260719_0024
Create Date: 2026-07-21 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0025"
down_revision = "20260719_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("users", "aftersale_requests"):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_deleted_by_user", table, "users", ["deleted_by_user_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"], unique=False)


def downgrade() -> None:
    for table in ("aftersale_requests", "users"):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_constraint(f"fk_{table}_deleted_by_user", table, type_="foreignkey")
        op.drop_column(table, "deleted_by_user_id")
        op.drop_column(table, "deleted_at")
