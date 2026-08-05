"""invalidate old sessions after internal account changes

Revision ID: 20260804_0033
Revises: 20260729_0032
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op


revision = "20260804_0033"
down_revision = "20260729_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("users", "session_version")
