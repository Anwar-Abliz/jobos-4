"""CLI script to seed pilot definitions into the JobOS graph.

Usage:
    python scripts/seed_pilots.py path/to/pilot.yaml
    python scripts/seed_pilots.py path/to/pilot.json
    python scripts/seed_pilots.py path/to/dir/   # seeds all YAML/JSON files
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("seed_pilots")


async def seed_one(path: Path) -> dict:
    """Parse and seed a single pilot file."""
    from jobos.kernel.pilot import parse_pilot_file
    from jobos.adapters.neo4j.connection import Neo4jConnection
    from jobos.adapters.neo4j.entity_repo import Neo4jEntityRepo
    from jobos.services.pilot_service import PilotService
    from jobos.config import get_settings

    pilot = parse_pilot_file(path)
    logger.info("Parsed pilot: %s (%s)", pilot.pilot_id, pilot.segment)

    settings = get_settings()
    conn = Neo4jConnection(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )
    await conn.connect()
    try:
        repo = Neo4jEntityRepo(conn)
        await repo.ensure_schema()
        svc = PilotService(graph=repo)
        result = await svc.seed_pilot(pilot)
        return result
    finally:
        await conn.close()


async def main(paths: list[str]) -> None:
    """Seed all given pilot files."""
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*.yaml")))
            files.extend(sorted(path.glob("*.yml")))
            files.extend(sorted(path.glob("*.json")))
        elif path.is_file():
            files.append(path)
        else:
            logger.error("Path not found: %s", path)

    if not files:
        logger.error("No pilot files found. Usage: python scripts/seed_pilots.py <path>")
        sys.exit(1)

    for f in files:
        logger.info("Seeding: %s", f)
        try:
            result = await seed_one(f)
            logger.info(
                "  -> %s: %d entities created (segment=%s, scenario=%s)",
                result.get("pilot_id"),
                result.get("total_entities", 0),
                result.get("segment_id"),
                result.get("scenario_id"),
            )
        except Exception as e:
            logger.error("  -> FAILED: %s", e)
            raise

    logger.info("Done. Seeded %d pilot file(s).", len(files))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_pilots.py <path_to_pilot_file_or_dir>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1:]))
