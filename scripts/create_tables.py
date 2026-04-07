"""Create PostgreSQL tables for JobOS 4.0."""
import asyncio
from jobos.adapters.postgres.connection import PostgresConnection
from jobos.adapters.postgres.models import Base
from jobos.config import get_settings


async def main():
    settings = get_settings()
    conn = PostgresConnection(settings.postgres.uri)
    await conn.connect()
    async with conn.engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    print("PostgreSQL tables created successfully.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
