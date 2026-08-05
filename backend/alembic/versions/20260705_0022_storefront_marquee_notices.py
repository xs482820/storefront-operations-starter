"""add storefront marquee notices

Revision ID: 20260705_0022
Revises: 20260516_0021
Create Date: 2026-07-05 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260705_0022"
down_revision = "20260516_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storefront_marquee_notices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_label", sa.String(length=24), nullable=False, server_default="查看"),
        sa.Column("action_type", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("action_value", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_storefront_marquee_notices_is_active", "storefront_marquee_notices", ["is_active"])
    op.create_index("ix_storefront_marquee_notices_sort_order", "storefront_marquee_notices", ["sort_order"])

    op.bulk_insert(
        sa.table(
            "storefront_marquee_notices",
            sa.column("title", sa.String),
            sa.column("body", sa.Text),
            sa.column("action_label", sa.String),
            sa.column("action_type", sa.String),
            sa.column("action_value", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "title": "今日下单满 299 元免配送费",
                "body": "系统会在结算页自动计算可用优惠，具体以提交订单为准。",
                "action_label": "去选购",
                "action_type": "category",
                "action_value": "all",
                "is_active": True,
                "sort_order": 10,
            },
            {
                "title": "批发客户可申请专属拿货价",
                "body": "完成商户认证后，可查看批发价和起批规则。",
                "action_label": "去认证",
                "action_type": "profile",
                "action_value": "wholesale",
                "is_active": True,
                "sort_order": 20,
            },
            {
                "title": "常购商品可先加入清单再统一结算",
                "body": "清单支持多规格数量调整，适合日常补货和批量采购。",
                "action_label": "看清单",
                "action_type": "cart",
                "action_value": "",
                "is_active": True,
                "sort_order": 30,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_storefront_marquee_notices_sort_order", table_name="storefront_marquee_notices")
    op.drop_index("ix_storefront_marquee_notices_is_active", table_name="storefront_marquee_notices")
    op.drop_table("storefront_marquee_notices")
