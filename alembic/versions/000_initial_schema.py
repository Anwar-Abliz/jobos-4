"""Alembic migration: Initial schema — base five PostgreSQL tables.

Revision: 000
Creates: metric_readings, vfe_readings, hiring_events, experiments, sessions.

This is the foundational migration. All subsequent migrations depend on this one.
Run before 001_add_job_metrics.py.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "000"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── metric_readings ──────────────────────────────────
    op.create_table(
        "metric_readings",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("metric_id", sa.String(36), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default=""),
        sa.Column("source", sa.String(50), nullable=False, server_default="user"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_metric_readings_entity_id", "metric_readings", ["entity_id"])
    op.create_index("ix_metric_readings_metric_id", "metric_readings", ["metric_id"])

    # ── vfe_readings ─────────────────────────────────────
    op.create_table(
        "vfe_readings",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("vfe_value", sa.Float(), nullable=False),
        sa.Column("efe_value", sa.Float(), nullable=True),
        sa.Column("policy_id", sa.String(36), nullable=True),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_vfe_readings_job_id", "vfe_readings", ["job_id"])

    # ── hiring_events ────────────────────────────────────
    op.create_table(
        "hiring_events",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("hirer_id", sa.String(36), nullable=False),
        sa.Column("hiree_id", sa.String(36), nullable=False),
        sa.Column("context_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "policy_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "causal_estimate",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_hiring_events_hirer_id", "hiring_events", ["hirer_id"])
    op.create_index("ix_hiring_events_hiree_id", "hiring_events", ["hiree_id"])

    # ── experiments ──────────────────────────────────────
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("assumption_id", sa.String(36), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column(
            "success_criteria",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "failure_criteria",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "results",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_experiments_assumption_id", "experiments", ["assumption_id"])

    # ── sessions ─────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("focus", sa.String(100), nullable=False, server_default="general"),
        sa.Column("goal_text", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(50), nullable=False, server_default="INIT"),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="'{}'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_index("ix_experiments_assumption_id", table_name="experiments")
    op.drop_table("experiments")
    op.drop_index("ix_hiring_events_hiree_id", table_name="hiring_events")
    op.drop_index("ix_hiring_events_hirer_id", table_name="hiring_events")
    op.drop_table("hiring_events")
    op.drop_index("ix_vfe_readings_job_id", table_name="vfe_readings")
    op.drop_table("vfe_readings")
    op.drop_index("ix_metric_readings_metric_id", table_name="metric_readings")
    op.drop_index("ix_metric_readings_entity_id", table_name="metric_readings")
    op.drop_table("metric_readings")
