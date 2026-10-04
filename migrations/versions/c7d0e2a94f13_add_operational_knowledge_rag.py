"""add operational knowledge RAG index

Revision ID: c7d0e2a94f13
Revises: b6e927c8d4a1
Create Date: 2026-09-28 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "c7d0e2a94f13"
down_revision: str | Sequence[str] | None = "b6e927c8d4a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service", "environment", "source", name="uq_knowledge_document_scope"
        ),
    )
    op.create_index(
        "ix_knowledge_documents_scope",
        "knowledge_documents",
        ["service", "environment"],
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunk_document_index"
        ),
    )
    op.create_index("ix_knowledge_chunks_document", "knowledge_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_scope", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
