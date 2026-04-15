"""Alembic env.py — JobOS 4.0.

Reads POSTGRES_URI from .env (via python-dotenv) and converts the
async URI (postgresql+asyncpg://) to a sync one (postgresql://) for
Alembic's synchronous migration runner.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to path so we can import models
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

# Import all ORM models so metadata knows about them
from jobos.adapters.postgres.models import Base

config = context.config

# Override sqlalchemy.url from environment
pg_uri = os.getenv("POSTGRES_URI", os.getenv(
    "DATABASE_URL", config.get_main_option("sqlalchemy.url", "")
))
# Convert async URI to sync for Alembic
sync_uri = pg_uri.replace("postgresql+asyncpg://", "postgresql://")
# Also handle Render's postgres:// shorthand
if sync_uri.startswith("postgres://"):
    sync_uri = sync_uri.replace("postgres://", "postgresql://", 1)
config.set_main_option("sqlalchemy.url", sync_uri)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
