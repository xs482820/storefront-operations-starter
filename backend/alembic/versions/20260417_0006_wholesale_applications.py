"""wholesale applications

Revision ID: 20260417_0006
Revises: 20260417_0005
Create Date: 2026-04-17 23:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260417_0006"
down_revision = "20260417_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wholesale_applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("review_note", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_wholesale_applications_user_id", "wholesale_applications", ["user_id"], unique=False)
    op.create_index("ix_wholesale_applications_status", "wholesale_applications", ["status"], unique=False)
    op.create_index("ix_wholesale_applications_reviewed_by", "wholesale_applications", ["reviewed_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wholesale_applications_reviewed_by", table_name="wholesale_applications")
    op.drop_index("ix_wholesale_applications_status", table_name="wholesale_applications")
    op.drop_index("ix_wholesale_applications_user_id", table_name="wholesale_applications")
    op.drop_table("wholesale_applications")
