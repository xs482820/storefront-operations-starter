"""store reusable image prompt templates

Revision ID: 20260728_0031
Revises: 20260728_0030
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op


revision = "20260728_0031"
down_revision = "20260728_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_image_prompt_templates_owner_user_id", "image_prompt_templates", ["owner_user_id"])


def downgrade() -> None:
    op.drop_table("image_prompt_templates")
