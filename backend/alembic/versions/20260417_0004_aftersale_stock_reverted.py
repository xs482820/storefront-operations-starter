"""aftersale stock reverted flag

Revision ID: 20260417_0004
Revises: 20260416_0003
Create Date: 2026-04-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260417_0004"
down_revision: str | Sequence[str] | None = "20260416_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "aftersale_requests",
        sa.Column("stock_reverted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("aftersale_requests", "stock_reverted")
