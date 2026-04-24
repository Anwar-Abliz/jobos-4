"""Alembic migration: Add hierarchy_versions table.

Revision: 006
Adds hierarchy_versions table for tracking hierarchy snapshots and diffs.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create hierarchy_versions table."""
    op.create_table(
        "hierarchy_versions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("scope_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "diff_from_previous",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_hierarchy_versions_scope_ver",
        "hierarchy_versions",
        ["scope_id", "version"],
    )


def downgrade() -> None:
    """Drop hierarchy_versions table."""
    op.drop_index(
        "ix_hierarchy_versions_scope_ver",
        table_name="hierarchy_versions",
    )
    op.drop_table("hierarchy_versions")
