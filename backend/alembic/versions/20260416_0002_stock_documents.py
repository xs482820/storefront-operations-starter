"""stock documents

Revision ID: 20260416_0002
Revises: 20260415_0001
Create Date: 2026-04-16 16:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260416_0002"
down_revision = "20260415_0001"
branch_labels = None
depends_on = None


stock_document_type = sa.Enum(
    "inbound",
    "outbound",
    "adjustment",
    "stocktake",
    name="stock_document_type",
)
stock_document_status = sa.Enum(
    "applied",
    name="stock_document_status",
)


def upgrade() -> None:
    op.create_table(
        "stock_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doc_no", sa.String(length=40), nullable=False),
        sa.Column("doc_type", stock_document_type, nullable=False),
        sa.Column("status", stock_document_status, nullable=False, server_default="applied"),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_base_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("doc_no", name="uq_stock_documents_doc_no"),
    )
    op.create_index("ix_stock_documents_doc_no", "stock_documents", ["doc_no"], unique=False)
    op.create_index("ix_stock_documents_doc_type", "stock_documents", ["doc_type"], unique=False)
    op.create_index("ix_stock_documents_status", "stock_documents", ["status"], unique=False)
    op.create_index("ix_stock_documents_operator_id", "stock_documents", ["operator_id"], unique=False)

    op.create_table(
        "stock_document_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("stock_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("delta_base_qty", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_stock_document_items_document_id", "stock_document_items", ["document_id"], unique=False)
    op.create_index("ix_stock_document_items_sku_id", "stock_document_items", ["sku_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_document_items_sku_id", table_name="stock_document_items")
    op.drop_index("ix_stock_document_items_document_id", table_name="stock_document_items")
    op.drop_table("stock_document_items")

    op.drop_index("ix_stock_documents_operator_id", table_name="stock_documents")
    op.drop_index("ix_stock_documents_status", table_name="stock_documents")
    op.drop_index("ix_stock_documents_doc_type", table_name="stock_documents")
    op.drop_index("ix_stock_documents_doc_no", table_name="stock_documents")
    op.drop_table("stock_documents")
