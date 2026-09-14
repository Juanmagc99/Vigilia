"""add durable investigations

Revision ID: a41c928c7f10
Revises: f36ac1b2d7e9
Create Date: 2026-09-07 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a41c928c7f10"
down_revision: Union[str, Sequence[str], None] = "f36ac1b2d7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("incidents", "revision", server_default=None)

    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("incident_revision", sa.Integer(), nullable=False),
        sa.Column("analyzer_version", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("result_schema", sa.String(), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigations_incident_id", "investigations", ["incident_id"])
    op.create_index("ix_investigations_status", "investigations", ["status"])
    op.create_index(
        "ix_investigations_next_attempt_at", "investigations", ["next_attempt_at"]
    )
    op.create_index(
        "ix_investigations_attempt_token", "investigations", ["attempt_token"]
    )
    op.create_index(
        "ix_investigations_lease_expires_at", "investigations", ["lease_expires_at"]
    )
    op.create_index(
        "ix_investigations_pending",
        "investigations",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "uq_investigations_active_revision_analyzer",
        "investigations",
        ["incident_id", "incident_revision", "analyzer_version"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'retry_wait')"),
    )
    op.create_index(
        "uq_investigations_incident_idempotency_key",
        "investigations",
        ["incident_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "investigation_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("attempt_token", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["investigation_id"], ["investigations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_token"),
    )
    op.create_index(
        "ix_investigation_attempts_investigation_id",
        "investigation_attempts",
        ["investigation_id"],
    )
    op.create_index(
        "uq_investigation_attempt_number",
        "investigation_attempts",
        ["investigation_id", "attempt_number"],
        unique=True,
    )

    op.create_table(
        "processed_events",
        sa.Column("consumer_name", sa.String(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer_name", "event_id"),
    )

    op.execute(
        """
        INSERT INTO investigations (
            id, incident_id, incident_revision, analyzer_version,
            idempotency_key, status, attempt_count, result_schema, result,
            error_code, error_message, requested_at, started_at, completed_at,
            next_attempt_at, attempt_token, lease_expires_at
        )
        SELECT
            reports.id,
            reports.incident_id,
            incidents.revision,
            'legacy/' || reports.model,
            NULL,
            'completed',
            0,
            'legacy_report.v1',
            jsonb_build_object('schema', 'legacy_report.v1', 'report', reports.content),
            NULL,
            NULL,
            reports.created_at,
            reports.created_at,
            reports.created_at,
            NULL,
            NULL,
            NULL
        FROM reports
        JOIN incidents ON incidents.id = reports.incident_id
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_index(
        "uq_investigation_attempt_number", table_name="investigation_attempts"
    )
    op.drop_index(
        "ix_investigation_attempts_investigation_id",
        table_name="investigation_attempts",
    )
    op.drop_table("investigation_attempts")
    op.drop_index(
        "uq_investigations_incident_idempotency_key", table_name="investigations"
    )
    op.drop_index(
        "uq_investigations_active_revision_analyzer", table_name="investigations"
    )
    op.drop_index("ix_investigations_pending", table_name="investigations")
    op.drop_index("ix_investigations_lease_expires_at", table_name="investigations")
    op.drop_index("ix_investigations_attempt_token", table_name="investigations")
    op.drop_index("ix_investigations_next_attempt_at", table_name="investigations")
    op.drop_index("ix_investigations_status", table_name="investigations")
    op.drop_index("ix_investigations_incident_id", table_name="investigations")
    op.drop_table("investigations")
    op.drop_column("incidents", "revision")
