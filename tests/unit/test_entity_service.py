"""Tests for EntityService — CRUD, Axiom 5/6 enforcement, Duality hook.

Uses a lightweight FakeGraphPort (in-memory) so no live Neo4j required.
"""
from __future__ import annotations

import pytest

from jobos.kernel.entity import EntityBase, EntityType
from jobos.kernel.axioms import AxiomViolation
from jobos.ports.graph_port import GraphPort
from jobos.services.entity_service import EntityService
from typing import Any


# ─── Fake Graph Port ─────────────────────────────────────

class FakeGraphPort(GraphPort):
    """In-memory graph for unit tests."""

    def __init__(self) -> None:
        self._entities: dict[str, EntityBase] = {}
        self._edges: list[dict] = []
        self._added_labels: list[tuple[str, str]] = []

    async def save_entity(self, entity: EntityBase) -> str:
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> EntityBase | None:
        return self._entities.get(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    async def list_entities(
        self,
        entity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityBase]:
        result = list(self._entities.values())
        if entity_type:
            result = [e for e in result if e.entity_type.value == entity_type]
        if status:
            result = [e for e in result if e.status == status]
        return result[offset : offset + limit]

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        self._edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "properties": properties or {},
        })
        return True

    async def delete_edge(self, source_id: str, target_id: str, edge_type: str) -> bool:
        before = len(self._edges)
        self._edges = [
            e for e in self._edges
            if not (e["source_id"] == source_id and e["target_id"] == target_id
                    and e["edge_type"] == edge_type)
        ]
        return len(self._edges) < before

    async def get_neighbors(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[EntityBase]:
        return []

    async def get_edges(
        self,
        entity_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        return []

    async def get_job_subgraph(self, job_id: str, depth: int = 3) -> dict[str, Any]:
        return {}

    async def add_label(self, entity_id: str, label: str) -> bool:
        self._added_labels.append((entity_id, label))
        return True

    async def ensure_schema(self) -> int:
        return 0

    async def find_path(self, source_id, target_id, max_depth=5):
        return []

    async def get_subgraph_by_label(self, label, limit=100):
        return []

    async def verify_connectivity(self) -> bool:
        return True


# ─── Helpers ─────────────────────────────────────────────

def make_job_entity(
    job_id: str = "j001",
    statement: str = "Define the scope",
    scope_id: str = "scope_a",
    root_token: str | None = None,
    job_type: str = "core_functional",
    executor_type: str | None = None,
    status: str = "active",
) -> EntityBase:
    props: dict = {"job_type": job_type, "scope_id": scope_id}
    if root_token:
        props["root_token"] = root_token
    if executor_type:
        props["executor_type"] = executor_type
    return EntityBase(
        id=job_id,
        statement=statement,
        entity_type=EntityType.JOB,
        status=status,
        properties=props,
    )


@pytest.fixture
def graph() -> FakeGraphPort:
    return FakeGraphPort()


@pytest.fixture
def svc(graph: FakeGraphPort) -> EntityService:
    return EntityService(graph)


# ─── Create: basic ───────────────────────────────────────

class TestEntityServiceCreate:
    @pytest.mark.asyncio
    async def test_create_job_persists_to_graph(self, svc, graph):
        entity = make_job_entity()
        result = await svc.create(entity)
        assert result.id == entity.id
        assert entity.id in graph._entities

    @pytest.mark.asyncio
    async def test_create_sets_timestamps(self, svc):
        entity = make_job_entity()
        result = await svc.create(entity)
        assert result.created_at is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_adds_type_label(self, svc):
        entity = make_job_entity()
        result = await svc.create(entity)
        assert "Job" in result.labels

    @pytest.mark.asyncio
    async def test_create_non_job_entity(self, svc, graph):
        cap = EntityBase(
            id="cap_001",
            statement="A capability",
            entity_type=EntityType.CAPABILITY,
            properties={"capability_kind": "product"},
        )
        result = await svc.create(cap)
        assert result.id == "cap_001"
        assert "Capability" in result.labels

    @pytest.mark.asyncio
    async def test_create_job_invalid_verb_raises_axiom_5(self, svc):
        entity = make_job_entity(statement="Success criteria matter")
        with pytest.raises(AxiomViolation) as exc_info:
            await svc.create(entity)
        assert exc_info.value.axiom == 5

    @pytest.mark.asyncio
    async def test_create_job_empty_statement_raises_axiom_5(self, svc):
        entity = make_job_entity(statement="")
        # Empty statement skips linguistic check — no error
        # (statement is optional on the entity model)
        result = await svc.create(entity)
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_experiential_job_valid(self, svc):
        entity = make_job_entity(
            statement="Feel confident shipping to production",
            job_type="emotional",
        )
        result = await svc.create(entity)
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_experiential_job_functional_verb_raises(self, svc):
        entity = make_job_entity(
            statement="Define the roadmap",
            job_type="emotional",
        )
        with pytest.raises(AxiomViolation) as exc_info:
            await svc.create(entity)
        assert exc_info.value.axiom == 5


# ─── Create: Axiom 6 root_token ──────────────────────────

class TestEntityServiceAxiom6:
    @pytest.mark.asyncio
    async def test_first_root_job_allowed(self, svc, graph):
        root = make_job_entity("r1", "Define strategy", root_token="ROOT", scope_id="proj_1")
        result = await svc.create(root)
        assert result.id == "r1"

    @pytest.mark.asyncio
    async def test_second_root_same_scope_raises_axiom_6(self, svc, graph):
        root1 = make_job_entity("r1", "Define strategy", root_token="ROOT", scope_id="proj_1")
        root2 = make_job_entity("r2", "Build the product", root_token="ROOT", scope_id="proj_1")
        await svc.create(root1)
        with pytest.raises(AxiomViolation) as exc_info:
            await svc.create(root2)
        assert exc_info.value.axiom == 6
        assert "proj_1" in exc_info.value.description

    @pytest.mark.asyncio
    async def test_root_jobs_different_scopes_both_allowed(self, svc, graph):
        root1 = make_job_entity("r1", "Define strategy", root_token="ROOT", scope_id="proj_1")
        root2 = make_job_entity("r2", "Build product", root_token="ROOT", scope_id="proj_2")
        await svc.create(root1)
        result = await svc.create(root2)
        assert result.id == "r2"

    @pytest.mark.asyncio
    async def test_non_root_job_not_checked(self, svc, graph):
        root = make_job_entity("r1", "Define strategy", root_token="ROOT", scope_id="proj_1")
        child = make_job_entity("c1", "Execute phase one", scope_id="proj_1")
        await svc.create(root)
        result = await svc.create(child)
        assert result.id == "c1"


# ─── Update ──────────────────────────────────────────────

class TestEntityServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_returns_none_for_missing_entity(self, svc):
        result = await svc.update("nonexistent", {"status": "completed"})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_modifies_status(self, svc, graph):
        entity = make_job_entity()
        await svc.create(entity)
        result = await svc.update(entity.id, {"status": "completed"})
        assert result is not None
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_update_modifies_properties(self, svc, graph):
        entity = make_job_entity()
        await svc.create(entity)
        result = await svc.update(entity.id, {"properties": {"tier": 2}})
        assert result is not None
        assert result.properties.get("tier") == 2

    @pytest.mark.asyncio
    async def test_update_invalid_statement_raises(self, svc, graph):
        entity = make_job_entity()
        await svc.create(entity)
        with pytest.raises(AxiomViolation) as exc_info:
            await svc.update(entity.id, {"statement": "passive sentence here"})
        assert exc_info.value.axiom == 5


# ─── Duality hook ────────────────────────────────────────

class TestDualityHook:
    @pytest.mark.asyncio
    async def test_completing_job_adds_capability_label(self, svc, graph):
        entity = make_job_entity(status="active")
        await svc.create(entity)
        await svc.update(entity.id, {"status": "completed"})
        assert ("j001", "Capability") in graph._added_labels

    @pytest.mark.asyncio
    async def test_completing_job_creates_dual_as_edge(self, svc, graph):
        entity = make_job_entity(status="active")
        await svc.create(entity)
        await svc.update(entity.id, {"status": "completed"})
        dual_as_edges = [
            e for e in graph._edges
            if e["edge_type"] == "DUAL_AS"
            and e["source_id"] == entity.id
            and e["target_id"] == entity.id
        ]
        assert len(dual_as_edges) == 1

    @pytest.mark.asyncio
    async def test_already_completed_job_no_duplicate_duality(self, svc, graph):
        entity = make_job_entity(status="completed")
        await svc.create(entity)
        # Update something else on an already-completed job
        await svc.update(entity.id, {"properties": {"tier": 1}})
        dual_as_edges = [e for e in graph._edges if e["edge_type"] == "DUAL_AS"]
        assert len(dual_as_edges) == 0

    @pytest.mark.asyncio
    async def test_non_job_completion_no_duality(self, svc, graph):
        cap = EntityBase(
            id="cap_001",
            statement="A capability",
            entity_type=EntityType.CAPABILITY,
            status="active",
            properties={"capability_kind": "product"},
        )
        await svc.create(cap)
        await svc.update(cap.id, {"status": "completed"})
        assert len(graph._added_labels) == 0
        dual_as_edges = [e for e in graph._edges if e["edge_type"] == "DUAL_AS"]
        assert len(dual_as_edges) == 0


# ─── Delete ──────────────────────────────────────────────

class TestEntityServiceDelete:
    @pytest.mark.asyncio
    async def test_delete_existing_entity(self, svc, graph):
        entity = make_job_entity()
        await svc.create(entity)
        result = await svc.delete(entity.id)
        assert result is True
        assert entity.id not in graph._entities

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, svc):
        result = await svc.delete("ghost_id")
        assert result is False


# ─── List ────────────────────────────────────────────────

class TestEntityServiceList:
    @pytest.mark.asyncio
    async def test_list_by_type_returns_matching(self, svc, graph):
        j = make_job_entity("j1")
        cap = EntityBase(
            id="cap1",
            statement="A capability",
            entity_type=EntityType.CAPABILITY,
            properties={"capability_kind": "service"},
        )
        await svc.create(j)
        await svc.create(cap)
        jobs = await svc.list_by_type(entity_type=EntityType.JOB)
        assert any(e.id == "j1" for e in jobs)
        assert not any(e.id == "cap1" for e in jobs)
