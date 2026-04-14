"""Alembic migration: Add job_metrics table (Dimension B — Evaluation Space).

Revision: 001
Creates: job_metrics table for SwitchEvaluator (Axiom 7) input data.

Columns:
    id                  VARCHAR(36)  PK
    job_id              VARCHAR(36)  NOT NULL
    timestamp           TIMESTAMPTZ  NOT NULL
    accuracy            FLOAT        nullable
    speed               FLOAT        nullable
    throughput          FLOAT        nullable
    bounds              JSONB        (per-metric lower/upper bounds)
    context_hash        VARCHAR(64)  nullable
    context_vector_ref  VARCHAR(36)  nullable

Indexes:
    ix_job_metrics_job_ts    (job_id, timestamp) — primary time-series query
    ix_job_metrics_accuracy  (accuracy)
    ix_job_metrics_speed     (speed)
    ix_job_metrics_throughput (throughput)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers
revision: str = "001"
down_revision: str | None = "000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the job_metrics table."""
    op.create_table(
        "job_metrics",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("throughput", sa.Float(), nullable=True),
        sa.Column("bounds", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column("context_hash", sa.String(64), nullable=True),
        sa.Column("context_vector_ref", sa.String(36), nullable=True),
    )

    # Composite time-series index (primary access pattern)
    op.create_index("ix_job_metrics_job_ts", "job_metrics", ["job_id", "timestamp"])

    # Individual metric indexes for SwitchEvaluator breach queries
    op.create_index("ix_job_metrics_accuracy", "job_metrics", ["accuracy"])
    op.create_index("ix_job_metrics_speed", "job_metrics", ["speed"])
    op.create_index("ix_job_metrics_throughput", "job_metrics", ["throughput"])


def downgrade() -> None:
    """Drop the job_metrics table and all its indexes."""
    op.drop_index("ix_job_metrics_throughput", table_name="job_metrics")
    op.drop_index("ix_job_metrics_speed", table_name="job_metrics")
    op.drop_index("ix_job_metrics_accuracy", table_name="job_metrics")
    op.drop_index("ix_job_metrics_job_ts", table_name="job_metrics")
    op.drop_table("job_metrics")
