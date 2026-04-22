"""JobOS 4.0 — SAP API Routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jobos.adapters.sap_simulation.ingestion_adapter import SAPIngestionAdapter
from jobos.api.deps import get_sap_ingestion_adapter

router = APIRouter(prefix="/sap")


class ProcessIngestRequest(BaseModel):
    template_name: str = ""
    template: dict[str, Any] | None = None


class OrgIngestRequest(BaseModel):
    structure: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    entity_id: str


@router.post("/ingest/process", response_model=IngestResponse)
async def ingest_process(
    request: ProcessIngestRequest,
    adapter: SAPIngestionAdapter = Depends(get_sap_ingestion_adapter),
):
    if request.template:
        template = request.template
    else:
        from jobos.adapters.sap_simulation.process_templates import ALL_TEMPLATES
        template = ALL_TEMPLATES.get(request.template_name.upper(), {})
        if not template:
            from fastapi import HTTPException
            available = list(ALL_TEMPLATES.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown template: {request.template_name}. Available: {available}",
            )

    entity_id = await adapter.ingest_process(template)
    return IngestResponse(entity_id=entity_id)


@router.post("/ingest/org-structure", response_model=IngestResponse)
async def ingest_org_structure(
    request: OrgIngestRequest,
    adapter: SAPIngestionAdapter = Depends(get_sap_ingestion_adapter),
):
    if request.structure:
        structure = request.structure
    else:
        from jobos.adapters.sap_simulation.org_structure import DEFAULT_ORG_STRUCTURE
        structure = DEFAULT_ORG_STRUCTURE

    entity_id = await adapter.ingest_org_structure(structure)
    return IngestResponse(entity_id=entity_id)


@router.get("/processes")
async def list_processes(
    adapter: SAPIngestionAdapter = Depends(get_sap_ingestion_adapter),
):
    entities = await adapter._graph.list_entities(entity_type="sap_process")
    return [
        {"id": e.id, "name": e.name, **e.properties}
        for e in entities
    ]


@router.get("/processes/{process_id}/context")
async def get_process_context(
    process_id: str,
    adapter: SAPIngestionAdapter = Depends(get_sap_ingestion_adapter),
):
    return await adapter.get_process_context(process_id)


@router.get("/processes/{process_id}/drift")
async def detect_drift(
    process_id: str,
    adapter: SAPIngestionAdapter = Depends(get_sap_ingestion_adapter),
):
    return await adapter.detect_context_drift(process_id)
