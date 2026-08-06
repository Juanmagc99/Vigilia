"""add outbox events

Revision ID: f36ac1b2d7e9
Revises: ea9da415cefa
Create Date: 2026-08-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f36ac1b2d7e9"
down_revision: Union[str, Sequence[str], None] = "ea9da415cefa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbox_events_available_at"), "outbox_events", ["available_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_claim_token"), "outbox_events", ["claim_token"], unique=False)
    op.create_index(op.f("ix_outbox_events_created_at"), "outbox_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_locked_until"), "outbox_events", ["locked_until"], unique=False)
    op.create_index(op.f("ix_outbox_events_published_at"), "outbox_events", ["published_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_topic"), "outbox_events", ["topic"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_events_topic"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_published_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_locked_until"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_created_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_claim_token"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_available_at"), table_name="outbox_events")
    op.drop_table("outbox_events")
