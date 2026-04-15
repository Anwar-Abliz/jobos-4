"""Alembic migration: Add experience_versions table (Dimension A versioning).

Revision: 002
Creates: experience_versions table for Experience marker versioning,
         supporting LLM generation, manual overrides, and history.

Columns:
    id          VARCHAR(36) PK
    job_id      VARCHAR(36) NOT NULL
    version     INTEGER     NOT NULL (auto-increment per job_id)
    markers     JSONB       NOT NULL (identity_phrases + emotion_phrases)
    source      VARCHAR(20) NOT NULL ("llm", "manual", "override")
    confidence  FLOAT       nullable
    created_by  VARCHAR(100) nullable
    created_at  TIMESTAMPTZ NOT NULL

Indexes:
    ix_experience_versions_job_ver  (job_id, version) — primary lookup
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic revision identifiers
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the experience_versions table."""
    op.create_table(
        "experience_versions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("markers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source", sa.String(20), nullable=False, server_default="llm"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_experience_versions_job_ver",
        "experience_versions",
        ["job_id", "version"],
    )


def downgrade() -> None:
    """Drop the experience_versions table."""
    op.drop_index("ix_experience_versions_job_ver", table_name="experience_versions")
    op.drop_table("experience_versions")
