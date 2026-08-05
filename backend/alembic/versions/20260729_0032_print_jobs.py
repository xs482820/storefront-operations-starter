"""store manual print tasks

Revision ID: 20260729_0032
Revises: 20260728_0031
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260729_0032"
down_revision = "20260728_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False, server_default="pick_list"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_device"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_print_jobs_order_id", "print_jobs", ["order_id"])
    op.create_index("ix_print_jobs_requested_by_user_id", "print_jobs", ["requested_by_user_id"])
    op.create_index("ix_print_jobs_status", "print_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("print_jobs")
