"""add unique index for customer phone

Revision ID: 20260417_0009
Revises: 20260417_0008
Create Date: 2026-04-17 18:25:00
"""

from alembic import op


revision = "20260417_0009"
down_revision = "20260417_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE customer_profiles SET phone = NULL WHERE phone = ''")
    op.execute(
        """
        WITH ranked AS (
            SELECT id, phone, ROW_NUMBER() OVER (PARTITION BY phone ORDER BY id) AS rn
            FROM customer_profiles
            WHERE phone IS NOT NULL
        )
        UPDATE customer_profiles AS cp
        SET phone = NULL
        FROM ranked
        WHERE cp.id = ranked.id AND ranked.rn > 1
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_customer_profiles_phone_not_null
        ON customer_profiles (phone)
        WHERE phone IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_customer_profiles_phone_not_null")
