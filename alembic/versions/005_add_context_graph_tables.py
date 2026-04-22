"""Add context graph tables.

Revision ID: 005
Revises: 004
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Decision traces
    op.create_table(
        "decision_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_entity_id", sa.String(36), nullable=False),
        sa.Column("context_snapshot", JSONB, server_default="{}"),
        sa.Column("rationale", sa.Text, server_default=""),
        sa.Column("policies_evaluated", JSONB, server_default="[]"),
        sa.Column("alternatives", JSONB, server_default="[]"),
        sa.Column("vfe_before", sa.Float, nullable=True),
        sa.Column("vfe_after", sa.Float, nullable=True),
        sa.Column("lineage", JSONB, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_decision_traces_actor", "decision_traces", ["actor"])
    op.create_index(
        "ix_decision_traces_target", "decision_traces", ["target_entity_id"]
    )

    # Survey responses
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("survey_id", sa.String(36), nullable=False),
        sa.Column("outcome_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("importance", sa.Float, nullable=False),
        sa.Column("satisfaction", sa.Float, nullable=False),
        sa.Column("opportunity_score", sa.Float, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_survey_responses_survey_outcome",
        "survey_responses",
        ["survey_id", "outcome_id"],
    )

    # Context snapshots
    op.create_table(
        "context_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("snapshot_data", JSONB, server_default="{}"),
        sa.Column("source", sa.String(50), server_default="system"),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_context_snapshots_entity", "context_snapshots", ["entity_id"]
    )

    # Data ingestion log
    op.create_table(
        "data_ingestion_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), nullable=False),
        sa.Column("records_ingested", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_data_ingestion_log_source", "data_ingestion_log", ["data_source_id"]
    )


def downgrade() -> None:
    op.drop_table("data_ingestion_log")
    op.drop_table("context_snapshots")
    op.drop_table("survey_responses")
    op.drop_table("decision_traces")
