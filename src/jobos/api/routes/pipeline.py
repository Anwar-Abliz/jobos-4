"""JobOS 4.0 — Universal Pipeline Routes.

Single and bulk ingestion endpoints that accept any input combination
and return hierarchies + context. Designed for both interactive and
machine-to-machine data flows.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobos.api.deps import get_hierarchy_service
from jobos.services.universal_ingestor import IngestRequest, UniversalIngestor
from jobos.services.bulk_ingestor import (
    BulkIngestor,
    BulkIngestRequest,
    SourceSpec,
)

router = APIRouter()


class TextIngestIn(BaseModel):
    """JSON body for text/URL ingestion (no file upload)."""
    text: str = ""
    url: str = ""
    urls: list[str] = Field(default_factory=list)
    domain: str = ""
    goal: str = ""


class BulkIngestIn(BaseModel):
    """JSON body for bulk ingestion from multiple sources."""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    domain: str = ""
    goal: str = ""
    merge_strategy: str = "combine"


class JsonRecordsIn(BaseModel):
    """JSON body for structured record ingestion (DB exports, API responses)."""
    records: list[dict[str, Any]] = Field(default_factory=list)
    domain: str = ""
    goal: str = ""
    id_field: str = "id"
    text_field: str = "description"


class CrawlIn(BaseModel):
    """JSON body for multi-URL crawling."""
    urls: list[str] = Field(default_factory=list)
    max_depth: int = 1
    max_pages: int = 10
    domain: str = ""
    goal: str = ""


def _get_ingestor() -> UniversalIngestor:
    try:
        return UniversalIngestor(hierarchy_service=get_hierarchy_service())
    except RuntimeError:
        return UniversalIngestor()


def _get_bulk() -> BulkIngestor:
    try:
        return BulkIngestor(hierarchy_service=get_hierarchy_service())
    except RuntimeError:
        return BulkIngestor()


@router.post("/pipeline/ingest")
async def pipeline_ingest(
    req: TextIngestIn | None = None,
    text: str = Form(default=""),
    url: str = Form(default=""),
    domain: str = Form(default=""),
    goal: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    """Universal ingestion — text, URL, files, or any combination."""
    file_tuples: list[tuple[bytes, str]] = []
    for f in files:
        if f.filename:
            content = await f.read()
            if len(content) > 10_000_000:
                raise HTTPException(413, f"File {f.filename} too large (max 10MB)")
            file_tuples.append((content, f.filename))

    if req and not file_tuples:
        ingest_req = IngestRequest(
            text=req.text, url=req.url, urls=req.urls,
            domain=req.domain, goal=req.goal,
        )
    else:
        ingest_req = IngestRequest(
            text=text, url=url, domain=domain,
            goal=goal, files=file_tuples,
        )

    if not ingest_req.text and not ingest_req.url and not ingest_req.urls and not ingest_req.files:
        raise HTTPException(400, "Provide at least one of: text, url, urls, or files")

    result = await _get_ingestor().ingest(ingest_req)
    return result.to_dict()


@router.post("/pipeline/bulk")
async def pipeline_bulk(req: BulkIngestIn) -> dict[str, Any]:
    """Bulk ingestion from multiple heterogeneous sources.

    Each source in the array specifies: type (text/url/json), content, and optional metadata.
    Results are merged according to merge_strategy (combine/separate/deduplicate).
    """
    if not req.sources:
        raise HTTPException(400, "No sources provided")

    sources = [
        SourceSpec(
            type=s.get("type", "text"),
            content=s.get("content", ""),
            filename=s.get("filename", ""),
            metadata=s.get("metadata", {}),
        )
        for s in req.sources
    ]

    bulk_req = BulkIngestRequest(
        sources=sources,
        domain=req.domain,
        goal=req.goal,
        merge_strategy=req.merge_strategy,
    )
    result = await _get_bulk().ingest_bulk(bulk_req)
    return result.to_dict()


@router.post("/pipeline/bulk/json")
async def pipeline_bulk_json(req: JsonRecordsIn) -> dict[str, Any]:
    """Ingest structured JSON records (database exports, API responses).

    Each record should have a text field (configurable via text_field param)
    that will be used as the job statement.
    """
    if not req.records:
        raise HTTPException(400, "No records provided")

    result = await _get_bulk().ingest_json_records(
        records=req.records,
        domain=req.domain,
        goal=req.goal,
        id_field=req.id_field,
        text_field=req.text_field,
    )
    return result.to_dict()


@router.post("/pipeline/bulk/zip")
async def pipeline_bulk_zip(
    file: UploadFile = File(...),
    domain: str = Form(default=""),
    goal: str = Form(default=""),
) -> dict[str, Any]:
    """Ingest all supported files from a zip archive."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Must upload a .zip file")

    content = await file.read()
    if len(content) > 50_000_000:
        raise HTTPException(413, "Zip too large (max 50MB)")

    result = await _get_bulk().ingest_zip(content, domain, goal)
    return result.to_dict()


@router.post("/pipeline/crawl")
async def pipeline_crawl(req: CrawlIn) -> dict[str, Any]:
    """Crawl multiple URLs and ingest extracted content.

    Follows links up to max_depth hops, processing up to max_pages total.
    """
    if not req.urls:
        raise HTTPException(400, "No URLs provided")

    result = await _get_bulk().crawl_urls(
        seed_urls=req.urls,
        max_depth=req.max_depth,
        max_pages=req.max_pages,
        domain=req.domain,
        goal=req.goal,
    )
    return result.to_dict()


@router.post("/pipeline/enrich")
async def pipeline_enrich(
    entity_ids: list[str] = [],
    scope_id: str = "",
) -> dict[str, Any]:
    """Run context enrichment on specified entities or entire scope.

    Infers missing relationships, scores context coverage, and
    detects cross-source overlaps.
    """
    from jobos.engines.context_enrichment import ContextEnrichmentEngine

    try:
        from jobos.api.deps import get_graph_port
        graph = get_graph_port()
    except RuntimeError:
        graph = None

    engine = ContextEnrichmentEngine(graph=graph)
    result = await engine.enrich(
        entity_ids=entity_ids or None,
        scope_id=scope_id,
    )
    return {
        "entities_enriched": result.entities_enriched,
        "relationships_inferred": result.relationships_inferred,
        "coverage_score": result.coverage_score,
        "cross_source_links": result.cross_source_links,
        "warnings": result.warnings,
        "details": result.details,
    }
