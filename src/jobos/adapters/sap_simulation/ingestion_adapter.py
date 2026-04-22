"""SAP Ingestion Adapter — Mock implementation of SAPIngestionPort.

Ingests SAP process templates and org structures into the entity graph.
"""
from __future__ import annotations

import logging
from typing import Any

from jobos.kernel.entity import EntityBase, EntityType, _uid
from jobos.ports.graph_port import GraphPort

logger = logging.getLogger(__name__)


class SAPIngestionAdapter:
    """Mock SAP ingestion that creates entities from templates."""

    def __init__(self, graph: GraphPort) -> None:
        self._graph = graph

    async def ingest_process(self, template: dict) -> str:
        """Ingest a process template into the entity graph.

        Creates:
        - 1 SAPProcess entity (parent)
        - N SAPTransaction entities (one per step)
        - N SAPObject entities (deduped)
        - Edges: EXECUTED_BY, OPERATES_ON, PRECEDED_BY

        Returns the process entity ID.
        """
        process_id = _uid()
        process_entity = EntityBase(
            id=process_id,
            name=template["name"],
            statement=f"Execute {template['name']} process",
            entity_type=EntityType.SAP_PROCESS,
            properties={
                "sap_module": template.get("sap_module", ""),
                "process_type": template.get("process_type", "e2e"),
                "automation_level": 0.0,
                "context_freshness": "snapshot",
            },
        )
        await self._graph.save_entity(process_entity)

        # Track created objects for deduplication
        created_objects: dict[str, str] = {}
        prev_tx_id: str | None = None

        for step in template.get("steps", []):
            # Create transaction entity
            tx_id = _uid()
            tx_entity = EntityBase(
                id=tx_id,
                name=step["name"],
                statement=f"Execute {step['name']}",
                entity_type=EntityType.SAP_TRANSACTION,
                properties={
                    "tcode": step.get("tcode", ""),
                    "fiori_app_id": step.get("fiori_app_id", ""),
                    "process_step": step["name"],
                    "automation_candidate": False,
                },
            )
            await self._graph.save_entity(tx_entity)
            await self._graph.create_edge(process_id, tx_id, "EXECUTED_BY")

            # Create/link business objects
            for obj_name in step.get("objects", []):
                if obj_name not in created_objects:
                    obj_id = _uid()
                    obj_entity = EntityBase(
                        id=obj_id,
                        name=obj_name,
                        statement=f"Business object: {obj_name}",
                        entity_type=EntityType.SAP_OBJECT,
                        properties={"object_type": obj_name},
                    )
                    await self._graph.save_entity(obj_entity)
                    created_objects[obj_name] = obj_id
                await self._graph.create_edge(
                    tx_id, created_objects[obj_name], "OPERATES_ON"
                )

            # Create sequence edges
            if prev_tx_id:
                await self._graph.create_edge(tx_id, prev_tx_id, "PRECEDED_BY")
            prev_tx_id = tx_id

        logger.info(
            "Ingested process '%s': %d steps, %d objects",
            template["name"],
            len(template.get("steps", [])),
            len(created_objects),
        )
        return process_id

    async def ingest_org_structure(self, structure: dict) -> str:
        """Ingest an org structure into the entity graph.

        Returns the company code entity ID.
        """
        cc = structure.get("company_code", structure)
        cc_id = _uid()
        cc_entity = EntityBase(
            id=cc_id,
            name=cc["name"],
            statement=f"Company: {cc['name']}",
            entity_type=EntityType.SAP_ORG_UNIT,
            properties={
                "unit_type": "company_code",
                "sap_code": cc.get("sap_code", ""),
                "country": cc.get("country", ""),
                "currency": cc.get("currency", ""),
            },
        )
        await self._graph.save_entity(cc_entity)

        # Plants
        for plant in cc.get("plants", []):
            p_id = _uid()
            p_entity = EntityBase(
                id=p_id,
                name=plant["name"],
                statement=f"Plant: {plant['name']}",
                entity_type=EntityType.SAP_ORG_UNIT,
                properties={
                    "unit_type": "plant",
                    "sap_code": plant.get("sap_code", ""),
                    "parent_unit_id": cc_id,
                    "country": plant.get("country", ""),
                },
            )
            await self._graph.save_entity(p_entity)
            await self._graph.create_edge(p_id, cc_id, "BELONGS_TO")

        # Sales orgs
        for so in cc.get("sales_orgs", []):
            so_id = _uid()
            so_entity = EntityBase(
                id=so_id,
                name=so["name"],
                statement=f"Sales org: {so['name']}",
                entity_type=EntityType.SAP_ORG_UNIT,
                properties={
                    "unit_type": "sales_org",
                    "sap_code": so.get("sap_code", ""),
                    "parent_unit_id": cc_id,
                    "country": so.get("country", ""),
                    "currency": so.get("currency", ""),
                },
            )
            await self._graph.save_entity(so_entity)
            await self._graph.create_edge(so_id, cc_id, "BELONGS_TO")

        # Purchasing orgs
        for po in cc.get("purchasing_orgs", []):
            po_id = _uid()
            po_entity = EntityBase(
                id=po_id,
                name=po["name"],
                statement=f"Purchasing org: {po['name']}",
                entity_type=EntityType.SAP_ORG_UNIT,
                properties={
                    "unit_type": "purchasing_org",
                    "sap_code": po.get("sap_code", ""),
                    "parent_unit_id": cc_id,
                    "country": po.get("country", ""),
                    "currency": po.get("currency", ""),
                },
            )
            await self._graph.save_entity(po_entity)
            await self._graph.create_edge(po_id, cc_id, "BELONGS_TO")

        logger.info(
            "Ingested org structure '%s': %d plants, %d sales orgs",
            cc["name"],
            len(cc.get("plants", [])),
            len(cc.get("sales_orgs", [])),
        )
        return cc_id

    async def get_process_context(self, process_id: str) -> dict[str, Any]:
        """Gather full context for a process: entity + neighbors + edges."""
        entity = await self._graph.get_entity(process_id)
        if not entity:
            return {}

        neighbors = await self._graph.get_neighbors(process_id, direction="both")
        edges = await self._graph.get_edges(process_id, direction="both")

        return {
            "entity": entity.model_dump(mode="json"),
            "neighbors": [n.model_dump(mode="json") for n in neighbors],
            "edges": edges,
        }

    async def detect_context_drift(self, process_id: str) -> dict[str, Any]:
        """Detect if context has drifted (placeholder — returns freshness status)."""
        entity = await self._graph.get_entity(process_id)
        if not entity:
            return {"drift_detected": False, "reason": "entity not found"}

        freshness = entity.properties.get("context_freshness", "snapshot")
        return {
            "drift_detected": freshness == "stale",
            "freshness": freshness,
            "entity_id": process_id,
        }
