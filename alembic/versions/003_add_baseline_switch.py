"""Alembic migration: Add baseline_snapshots and switch_events tables.

Revision: 003
Creates: baseline_snapshots and switch_events tables for scenario
         metric baseline tracking and switch event recording.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create baseline_snapshots and switch_events tables."""
    op.create_table(
        "baseline_snapshots",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column("bounds", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("captured_by", sa.String(100), nullable=True),
    )
    op.create_index("ix_baseline_snapshots_scenario", "baseline_snapshots", ["scenario_id"])

    op.create_table(
        "switch_events",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("trigger_metric", sa.String(100), nullable=False),
        sa.Column("trigger_value", sa.Float(), nullable=False),
        sa.Column("trigger_bound", sa.String(100), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
    )
    op.create_index("ix_switch_events_scenario", "switch_events", ["scenario_id"])


def downgrade() -> None:
    """Drop switch_events and baseline_snapshots tables."""
    op.drop_index("ix_switch_events_scenario", table_name="switch_events")
    op.drop_table("switch_events")
    op.drop_index("ix_baseline_snapshots_scenario", table_name="baseline_snapshots")
    op.drop_table("baseline_snapshots")
