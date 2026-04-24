"""JobOS 4.0 — SOP/Workflow Ingestion Routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from jobos.services.sop_ingestion_service import SOPIngestionService

router = APIRouter()


class TextIngestionIn(BaseModel):
    text: str = Field(..., min_length=10)
    domain: str = ""


@router.post("/ingest/document")
async def ingest_document(file: UploadFile = File(...)):
    """Upload a document (PDF, DOCX, TXT) and convert to job hierarchy."""
    if not file.filename:
        raise HTTPException(400, "Filename required")

    content = await file.read()
    if len(content) > 10_000_000:
        raise HTTPException(413, "File too large (max 10MB)")

    svc = SOPIngestionService()
    result = await svc.ingest_document(content, file.filename)
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result


@router.post("/ingest/text")
async def ingest_text(req: TextIngestionIn):
    """Convert raw text (SOP, process description) into job hierarchy."""
    svc = SOPIngestionService()
    result = await svc.ingest_from_text(req.text, req.domain)
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result
