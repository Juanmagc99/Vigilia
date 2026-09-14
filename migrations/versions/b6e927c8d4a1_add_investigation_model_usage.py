"""add investigation model usage

Revision ID: b6e927c8d4a1
Revises: a41c928c7f10
Create Date: 2026-09-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6e927c8d4a1"
down_revision: str | Sequence[str] | None = "a41c928c7f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "investigation_attempts", sa.Column("provider", sa.String(), nullable=True)
    )
    op.add_column(
        "investigation_attempts", sa.Column("model", sa.String(), nullable=True)
    )
    op.add_column(
        "investigation_attempts",
        sa.Column("provider_response_id", sa.String(), nullable=True),
    )
    op.add_column(
        "investigation_attempts",
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investigation_attempts",
        sa.Column("cached_prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investigation_attempts",
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investigation_attempts", sa.Column("total_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "investigation_attempts",
        sa.Column("estimated_cost_usd", sa.Numeric(14, 8), nullable=True),
    )
    op.add_column(
        "investigation_attempts", sa.Column("latency_ms", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("investigation_attempts", "latency_ms")
    op.drop_column("investigation_attempts", "estimated_cost_usd")
    op.drop_column("investigation_attempts", "total_tokens")
    op.drop_column("investigation_attempts", "completion_tokens")
    op.drop_column("investigation_attempts", "cached_prompt_tokens")
    op.drop_column("investigation_attempts", "prompt_tokens")
    op.drop_column("investigation_attempts", "provider_response_id")
    op.drop_column("investigation_attempts", "model")
    op.drop_column("investigation_attempts", "provider")
