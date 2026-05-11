"""Seed the Managerial Job Catalog (13 T-1 + 36 T-2) into Neo4j.

Usage:
    cd C:\\my-codes\\jobos-4
    python scripts/seed_managerial_catalog.py

Requires: Neo4j connection configured via .env (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.jobos.kernel.entity import EntityBase, EntityType
from src.jobos.adapters.neo4j.connection import Neo4jConnection
from src.jobos.adapters.neo4j.entity_repo import Neo4jEntityRepo
from src.jobos.config import JobOSSettings


SPEC_PATH = Path(__file__).parent.parent / "spec" / "jobos-ai-spec.json"
SCOPE_ID = "managerial_catalog_v1"


async def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    catalog = spec["managerial_catalog"]

    settings = JobOSSettings()
    conn = Neo4jConnection(settings.neo4j)
    await conn.connect()
    repo = Neo4jEntityRepo(conn)
    await repo.ensure_schema()

    t1_entries = catalog["t1"]
    t2_entries = catalog["t2"]

    print(f"Seeding {len(t1_entries)} T-1 pillars and {len(t2_entries)} T-2 entries...")

    t1_id_map: dict[str, str] = {}

    for entry in t1_entries:
        entity = EntityBase(
            name=entry["name"],
            statement=f"Direct organizational efforts toward {entry['name'].lower()}",
            entity_type=EntityType.JOB,
            status="active",
            labels=["Job"],
            properties={
                "job_type": "managerial",
                "job_nature": "project",
                "level": 0,
                "tier": 1,
                "root_token": "ROOT",
                "scope_id": SCOPE_ID,
                "vfe_current": 0.0,
                "catalog_id": entry["id"],
                "definition": entry["definition"],
                "rationale": entry.get("rationale", ""),
                "slug": entry["id"].lower().replace("-", "_"),
            },
            provenance="import",
        )
        saved_id = await repo.save_entity(entity)
        t1_id_map[entry["id"]] = entity.id
        print(f"  T-1: {entry['id']} — {entry['name']} → {entity.id}")

    for entry in t2_entries:
        parent_t1_id = entry.get("parent_t1_id", "")
        parent_entity_id = t1_id_map.get(parent_t1_id, "")

        entity = EntityBase(
            name=entry["name"],
            statement=f"Execute {entry['name'].lower()} within the organization",
            entity_type=EntityType.JOB,
            status="active",
            labels=["Job"],
            properties={
                "job_type": "managerial",
                "job_nature": "project",
                "level": 1,
                "tier": 2,
                "scope_id": SCOPE_ID,
                "vfe_current": 0.0,
                "catalog_id": entry["id"],
                "definition": entry["definition"],
                "parent_t1_id": parent_t1_id,
                "slug": entry["id"].lower().replace("-", "_"),
            },
            provenance="import",
        )
        await repo.save_entity(entity)
        print(f"  T-2: {entry['id']} — {entry['name']} (parent: {parent_t1_id}) → {entity.id}")

        if parent_entity_id:
            await repo.create_edge(
                source_id=entity.id,
                target_id=parent_entity_id,
                edge_type="PART_OF",
                properties={"catalog_version": "v1", "relationship": "managerial_hierarchy"},
            )

    await conn.close()
    print(f"\nDone. Seeded {len(t1_entries)} T-1 + {len(t2_entries)} T-2 = {len(t1_entries) + len(t2_entries)} entities.")
    print(f"Scope ID: {SCOPE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
