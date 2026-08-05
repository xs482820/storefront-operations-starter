"""store employee image generation history

Revision ID: 20260728_0030
Revises: 20260725_0029
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260728_0030"
down_revision = "20260725_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_generation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("reference_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result_url", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_image_generation_history_user_id", "image_generation_history", ["user_id"])
    op.create_index("ix_image_generation_history_status", "image_generation_history", ["status"])


def downgrade() -> None:
    op.drop_table("image_generation_history")
