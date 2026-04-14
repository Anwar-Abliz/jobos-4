"""JobOS 4.0 — Extraction Routes.

POST /api/extract/url      — extract content from a URL
POST /api/extract/document  — extract content from an uploaded file
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobos.adapters.extraction.context_builder import build_context_from_text
from jobos.adapters.extraction.csv_hierarchy_parser import (
    detect_hierarchy_csv,
    parse_hierarchy_csv,
)
from jobos.adapters.extraction.document_extractor import (
    SUPPORTED_EXTENSIONS,
    extract_from_bytes,
)
from jobos.adapters.extraction.url_extractor import AuthWallError, extract_from_url
from jobos.api.deps import _llm

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Models ──────────────────────────────────────────────

class UrlRequest(BaseModel):
    url: str = Field(..., description="URL to extract content from")


class ContextOut(BaseModel):
    who: str = ""
    why: str = ""
    what: str = ""
    where: str = ""
    when: str = ""
    how: str = ""


class HierarchyJobOut(BaseModel):
    id: str
    tier: str
    statement: str
    category: str = ""
    rationale: str = ""
    metrics_hint: list[str] = Field(default_factory=list)


class HierarchyEdgeOut(BaseModel):
    parent_id: str
    child_id: str
    strength: float = 1.0


class ParsedHierarchy(BaseModel):
    """Pre-parsed hierarchy from structured input (e.g. ODI-style CSV)."""
    domain: str
    jobs: list[HierarchyJobOut]
    edges: list[HierarchyEdgeOut]
    summary: dict[str, int] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    text: str
    title: str
    source: str
    context: ContextOut
    keywords: list[str] = Field(default_factory=list)
    job_hints: list[str] = Field(default_factory=list)
    hierarchy: ParsedHierarchy | None = None


# ─── Routes ──────────────────────────────────────────────

@router.post("/extract/url", response_model=ExtractionResponse)
async def extract_url(body: UrlRequest) -> ExtractionResponse:
    """Fetch a URL and extract structured content + 5W1H context."""
    try:
        content = await extract_from_url(body.url)
    except AuthWallError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.error("URL extraction failed: %s", e)
        error_msg = str(e)
        if "401" in error_msg or "403" in error_msg:
            error_msg = (
                f"Access denied ({error_msg}). "
                "This URL likely requires authentication (e.g. Teams, SharePoint). "
                "Try copying the page content and pasting it in the Text tab instead."
            )
        elif "404" in error_msg:
            error_msg = f"Page not found ({error_msg}). Check the URL and try again."
        elif "ConnectError" in error_msg or "ConnectTimeout" in error_msg:
            error_msg = (
                f"Could not connect to the URL ({error_msg}). "
                "The site may be behind a firewall or VPN."
            )
        raise HTTPException(status_code=422, detail=error_msg) from e

    ctx = await build_context_from_text(content.text, llm=_llm)

    return ExtractionResponse(
        text=content.text[:3000],
        title=content.title,
        source=content.source,
        context=ContextOut(
            who=ctx.who, why=ctx.why, what=ctx.what,
            where=ctx.where, when=ctx.when, how=ctx.how,
        ),
        keywords=ctx.keywords,
        job_hints=ctx.job_hints,
    )


@router.post("/extract/document", response_model=ExtractionResponse)
async def extract_document(
    file: UploadFile,
) -> ExtractionResponse:
    """Upload a document and extract structured content + 5W1H context."""
    filename = file.filename or "unknown.txt"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if f".{ext}" not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '.{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    try:
        raw = await file.read()
        content = extract_from_bytes(raw, filename)
    except Exception as e:
        logger.error("Document extraction failed: %s", e)
        raise HTTPException(
            status_code=422, detail=f"Failed to extract from document: {e}"
        ) from e

    # Check if this is a structured hierarchy CSV
    parsed_hierarchy: ParsedHierarchy | None = None
    if ext == "csv" and detect_hierarchy_csv(content.text):
        parsed = parse_hierarchy_csv(content.text)
        if parsed:
            parsed_hierarchy = ParsedHierarchy(
                domain=parsed["domain"],
                jobs=[HierarchyJobOut(**j) for j in parsed["jobs"]],
                edges=[HierarchyEdgeOut(**e) for e in parsed["edges"]],
                summary=parsed["summary"],
            )
            logger.info(
                "Parsed structured hierarchy from CSV: %d jobs, %d edges",
                len(parsed["jobs"]),
                len(parsed["edges"]),
            )

    ctx = await build_context_from_text(content.text, llm=_llm)

    return ExtractionResponse(
        text=content.text[:3000],
        title=content.title,
        source=content.source,
        context=ContextOut(
            who=ctx.who, why=ctx.why, what=ctx.what,
            where=ctx.where, when=ctx.when, how=ctx.how,
        ),
        keywords=ctx.keywords,
        job_hints=ctx.job_hints,
        hierarchy=parsed_hierarchy,
    )
