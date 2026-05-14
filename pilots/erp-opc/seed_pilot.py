"""Seed the ERP-for-OPC Financial Close pilot hierarchy into Neo4j.

Usage:
    cd C:\\my-codes\\jobos-4
    python pilots/erp-opc/seed_pilot.py

Requires: Neo4j connection configured via .env (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from src.jobos.kernel.entity import EntityBase, EntityType
from src.jobos.kernel.t3_dsl import parse_constraint, T3ConstraintA, T3ConstraintB, T3ConstraintC
from src.jobos.adapters.neo4j.connection import Neo4jConnection
from src.jobos.adapters.neo4j.entity_repo import Neo4jEntityRepo

PILOT_DIR = Path(__file__).parent
HIERARCHY_PATH = PILOT_DIR / "hierarchy.json"
CONSTRAINTS_PATH = PILOT_DIR / "constraints.json"
SCOPE_ID = "pilot_erp_opc_v1"


async def main() -> None:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    hierarchy = json.loads(HIERARCHY_PATH.read_text(encoding="utf-8"))
    constraints = json.loads(CONSTRAINTS_PATH.read_text(encoding="utf-8"))

    conn = Neo4jConnection(
        uri=os.getenv("NEO4J_URI", ""),
        user=os.getenv("NEO4J_USER", ""),
        password=os.getenv("NEO4J_PASSWORD", ""),
    )
    await conn.connect()
    repo = Neo4jEntityRepo(conn)
    await repo.ensure_schema()

    mh = hierarchy["managerial_hierarchy"]
    t1_data = mh["t1"]
    t2_entries = mh["t2"]

    print(f"=== ERP-for-OPC Pilot: Seeding {1} T-1 + {len(t2_entries)} T-2 + {len(constraints['constraints'])} T-3 ===\n")

    # Seed T-1
    t1_entity = EntityBase(
        name=t1_data["name"],
        statement=t1_data["definition"],
        entity_type=EntityType.JOB,
        status="active",
        labels=["Job"],
        properties={
            "job_type": "managerial",
            "job_nature": "project",
            "level": 0,
            "tier": 1,
            "scope_id": SCOPE_ID,
            "pilot_id": hierarchy["pilot_id"],
            "catalog_id": t1_data["id"],
            "parent_apqc": t1_data["parent_apqc"],
            "domain": hierarchy["domain"],
            "primary_user": hierarchy["primary_user"],
        },
        provenance="pilot_seed",
    )
    await repo.save_entity(t1_entity)
    print(f"  T-1: {t1_data['id']} — {t1_data['name']} → {t1_entity.id}")

    # Seed T-2 entries
    t2_id_map: dict[str, str] = {}
    for entry in t2_entries:
        entity = EntityBase(
            name=entry["name"],
            statement=entry["definition"],
            entity_type=EntityType.JOB,
            status="active",
            labels=["Job"],
            properties={
                "job_type": "managerial",
                "job_nature": "project",
                "level": 1,
                "tier": 2,
                "scope_id": SCOPE_ID,
                "pilot_id": hierarchy["pilot_id"],
                "catalog_id": entry["id"],
                "parent_catalog_id": entry["parent"],
                "universal_steps": entry["universal_steps"],
            },
            provenance="pilot_seed",
        )
        await repo.save_entity(entity)
        t2_id_map[entry["id"]] = entity.id

        # Link T-2 → T-1
        await repo.create_edge(
            source_id=entity.id,
            target_id=t1_entity.id,
            edge_type="PART_OF",
            properties={"relationship": "pilot_hierarchy", "scope_id": SCOPE_ID},
        )
        print(f"  T-2: {entry['id']} — {entry['name']} → {entity.id}")

    # Seed T-3 constraints
    print()
    for c_data in constraints["constraints"]:
        parsed = parse_constraint(c_data["statement"])
        if parsed is None:
            print(f"  SKIP (parse failed): {c_data['id']}")
            continue

        pattern_label = c_data["pattern"]
        entity = EntityBase(
            name=f"Constraint: {c_data['id']}",
            statement=c_data["statement"],
            entity_type=EntityType.JOB,
            status="active",
            labels=["Job", "Constraint"],
            properties={
                "job_type": "constraint",
                "tier": 3,
                "scope_id": SCOPE_ID,
                "pilot_id": hierarchy["pilot_id"],
                "catalog_id": c_data["id"],
                "pattern": pattern_label,
                "parent_catalog_id": c_data["parent_t2"],
                "threshold": parsed.threshold,
                "unit": parsed.unit.value if hasattr(parsed, "unit") else "",
                "constraint_dict": parsed.to_dict(),
            },
            provenance="pilot_seed",
        )
        await repo.save_entity(entity)

        # Link T-3 → parent T-2 (or T-1 for top-level constraints)
        parent_id = t2_id_map.get(c_data["parent_t2"]) or t1_entity.id
        await repo.create_edge(
            source_id=entity.id,
            target_id=parent_id,
            edge_type="CONSTRAINS",
            properties={"scope_id": SCOPE_ID, "pattern": pattern_label},
        )
        print(f"  T-3: {c_data['id']} ({pattern_label}) → {entity.id}")

    # Seed agent capability nodes
    print()
    ah = hierarchy["agent_hierarchy"]
    agent_program = ah["t1_program"]
    agent_entity = EntityBase(
        name=agent_program["program_name"],
        statement=agent_program["description"],
        entity_type=EntityType.JOB,
        status="active",
        labels=["Job", "AgentProgram"],
        properties={
            "job_type": "agent",
            "tier": 1,
            "scope_id": SCOPE_ID,
            "catalog_id": agent_program["id"],
            "pilot_id": hierarchy["pilot_id"],
        },
        provenance="pilot_seed",
    )
    await repo.save_entity(agent_entity)
    print(f"  Agent T-1: {agent_program['id']} — {agent_program['program_name']} → {agent_entity.id}")

    for cap in ah["capabilities"]:
        cap_entity = EntityBase(
            name=cap["name"],
            statement=cap["description"],
            entity_type=EntityType.JOB,
            status="active",
            labels=["Job", "AgentCapability"],
            properties={
                "job_type": "agent_capability",
                "tier": 2,
                "scope_id": SCOPE_ID,
                "catalog_id": cap["id"],
                "pilot_id": hierarchy["pilot_id"],
                "input": cap["input"],
                "output": cap["output"],
                "escalation_trigger": cap["escalation_trigger"],
            },
            provenance="pilot_seed",
        )
        await repo.save_entity(cap_entity)
        await repo.create_edge(
            source_id=cap_entity.id,
            target_id=agent_entity.id,
            edge_type="PART_OF",
            properties={"scope_id": SCOPE_ID},
        )
        print(f"  Agent CAP: {cap['id']} — {cap['name']} → {cap_entity.id}")

    # Seed crosswalk edges
    print()
    for cw in hierarchy["crosswalk"]:
        managerial_entity_id = t2_id_map.get(cw["managerial"])
        if managerial_entity_id:
            await repo.create_edge(
                source_id=managerial_entity_id,
                target_id=agent_entity.id,
                edge_type="MAPS_TO_AGENT",
                properties={
                    "scope_id": SCOPE_ID,
                    "mapping_rule": cw["mapping_rule"],
                    "translation_type": cw["translation_type"],
                    "lossless": cw["lossless"],
                    "agent_capability": cw["agent_capability"],
                },
            )
            print(f"  Crosswalk: {cw['id']} — {cw['managerial']} → {cw['agent_capability']}")

    await conn.close()

    total = 1 + len(t2_entries) + len(constraints["constraints"]) + 1 + len(ah["capabilities"])
    print(f"\n=== Done. Seeded {total} entities + crosswalk edges. Scope: {SCOPE_ID} ===")


if __name__ == "__main__":
    asyncio.run(main())
