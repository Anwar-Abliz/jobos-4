"""JobOS 4.0 — Entity CRUD Routes (unified).

Single endpoint set for all entity types. The entity_type field
in the request body determines which property schema is enforced.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from jobos.kernel.entity import EntityBase, EntityType, validate_entity
from jobos.kernel.axioms import AxiomViolation
from jobos.api.deps import get_entity_service
from jobos.services.entity_service import EntityService

router = APIRouter()


# ─── Request / Response Models ───────────────────────────

class EntityCreateIn(BaseModel):
    """Request body for creating an Entity."""
    name: str = ""
    statement: str = ""
    entity_type: EntityType
    status: str = "active"
    properties: dict[str, Any] = Field(default_factory=dict)


class EntityUpdateIn(BaseModel):
    """Request body for updating an Entity."""
    name: str | None = None
    statement: str | None = None
    status: str | None = None
    properties: dict[str, Any] | None = None


class EntityOut(BaseModel):
    """Response model for an Entity."""
    id: str
    name: str
    statement: str
    entity_type: EntityType
    status: str
    properties: dict[str, Any]
    labels: list[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ─── Endpoints ───────────────────────────────────────────

@router.post("/entities", response_model=EntityOut, status_code=201)
async def create_entity(req: EntityCreateIn) -> EntityOut:
    """Create a new Entity.

    The entity_type determines which property schema is enforced.
    For Jobs (entity_type='job'), the statement must start with an action verb (Axiom 5).
    """
    svc = get_entity_service()
    entity = EntityBase(
        name=req.name,
        statement=req.statement,
        entity_type=req.entity_type,
        status=req.status,
        properties=req.properties,
    )
    try:
        created = await svc.create(entity)
    except AxiomViolation as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_out(created)


@router.get("/entities/{entity_id}", response_model=EntityOut)
async def get_entity(entity_id: str) -> EntityOut:
    """Retrieve an Entity by ID."""
    svc = get_entity_service()
    entity = await svc.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _to_out(entity)


@router.put("/entities/{entity_id}", response_model=EntityOut)
async def update_entity(entity_id: str, req: EntityUpdateIn) -> EntityOut:
    """Update an Entity's properties."""
    svc = get_entity_service()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        entity = await svc.update(entity_id, updates)
    except AxiomViolation as e:
        raise HTTPException(status_code=422, detail=str(e))
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _to_out(entity)


@router.delete("/entities/{entity_id}", status_code=204)
async def delete_entity(entity_id: str) -> None:
    """Delete an Entity and its incident edges."""
    svc = get_entity_service()
    found = await svc.delete(entity_id)
    if not found:
        raise HTTPException(status_code=404, detail="Entity not found")


@router.get("/entities", response_model=list[EntityOut])
async def list_entities(
    entity_type: EntityType | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[EntityOut]:
    """List entities with optional type/status filtering."""
    svc = get_entity_service()
    entities = await svc.list_by_type(
        entity_type=entity_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [_to_out(e) for e in entities]


# ─── Helpers ─────────────────────────────────────────────

def _to_out(entity: EntityBase) -> EntityOut:
    return EntityOut(
        id=entity.id,
        name=entity.name,
        statement=entity.statement,
        entity_type=entity.entity_type,
        status=entity.status,
        properties=entity.properties,
        labels=entity.labels,
        created_at=entity.created_at.isoformat(),
        updated_at=entity.updated_at.isoformat(),
    )
