"""add user blacklist and flag fields

Revision ID: 20260425_0015
Revises: 20260425_0014
Create Date: 2026-04-25 19:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260425_0015"
down_revision = "20260425_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("users", "is_flagged")
    op.drop_column("users", "is_blacklisted")

