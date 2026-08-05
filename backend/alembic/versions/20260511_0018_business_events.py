"""add business events ledger

Revision ID: 20260511_0018
Revises: 20260510_0017
Create Date: 2026-05-11 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260511_0018"
down_revision = "20260510_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_no", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_no", sa.String(length=64), nullable=True),
        sa.Column("action_code", sa.String(length=64), nullable=False),
        sa.Column("action_label", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=True),
        sa.Column("actor_name_snapshot", sa.String(length=64), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="internal"),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("event_no", name="uq_business_events_event_no"),
        sa.UniqueConstraint("request_id", name="uq_business_events_request_id"),
    )
    op.create_index("ix_business_events_entity_type", "business_events", ["entity_type"], unique=False)
    op.create_index("ix_business_events_entity_id", "business_events", ["entity_id"], unique=False)
    op.create_index("ix_business_events_entity_no", "business_events", ["entity_no"], unique=False)
    op.create_index("ix_business_events_action_code", "business_events", ["action_code"], unique=False)
    op.create_index("ix_business_events_source", "business_events", ["source"], unique=False)
    op.create_index("ix_business_events_actor_user_id", "business_events", ["actor_user_id"], unique=False)
    op.create_index("ix_business_events_visibility", "business_events", ["visibility"], unique=False)
    op.create_index("ix_business_events_correlation_id", "business_events", ["correlation_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for the business events migration")
