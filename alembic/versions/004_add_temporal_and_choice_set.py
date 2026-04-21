"""Alembic migration: Add bi-temporal columns and choice_set_snapshot.

Revision: 004
Adds event_time and ingestion_time to metric_readings, vfe_readings,
hiring_events, and switch_events.  Adds choice_set_snapshot JSONB
column to hiring_events.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add bi-temporal columns and choice_set_snapshot."""
    # metric_readings
    op.add_column(
        "metric_readings",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "metric_readings",
        sa.Column(
            "ingestion_time",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )

    # vfe_readings
    op.add_column(
        "vfe_readings",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "vfe_readings",
        sa.Column(
            "ingestion_time",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )

    # hiring_events
    op.add_column(
        "hiring_events",
        sa.Column(
            "choice_set_snapshot",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "hiring_events",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hiring_events",
        sa.Column(
            "ingestion_time",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )

    # switch_events
    op.add_column(
        "switch_events",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "switch_events",
        sa.Column(
            "ingestion_time",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    """Remove bi-temporal columns and choice_set_snapshot."""
    op.drop_column("switch_events", "ingestion_time")
    op.drop_column("switch_events", "event_time")

    op.drop_column("hiring_events", "ingestion_time")
    op.drop_column("hiring_events", "event_time")
    op.drop_column("hiring_events", "choice_set_snapshot")

    op.drop_column("vfe_readings", "ingestion_time")
    op.drop_column("vfe_readings", "event_time")

    op.drop_column("metric_readings", "ingestion_time")
    op.drop_column("metric_readings", "event_time")
