"""JobOS 4.0 — Chat Route (Conversational Interface).

POST /api/chat — the main user interaction endpoint.
Runs the full LLM-driven chat pipeline:
    INTERPRET → GROUND → ANALYZE → RESPOND
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobos.api.deps import get_chat_pipeline

router = APIRouter()


# ─── Request / Response Models ───────────────────────────

class ChatIn(BaseModel):
    """Chat request."""
    message: str = Field(..., max_length=4000)
    session_id: str | None = None
    job_id: str | None = None


class ChatOut(BaseModel):
    """Chat response."""
    session_id: str
    assistant_message: str
    intent: str
    entities_created: list[dict[str, Any]] = Field(default_factory=list)
    entities_updated: list[dict[str, Any]] = Field(default_factory=list)
    imperfections: list[dict[str, Any]] = Field(default_factory=list)
    vfe_current: float | None = None
    top_blocker: dict[str, Any] | None = None


# ─── Endpoint ────────────────────────────────────────────

@router.post("/chat", response_model=ChatOut)
async def chat(req: ChatIn) -> ChatOut:
    """Conversational interface to JobOS.

    Send a natural language message. The system will:
    1. Extract entities (jobs, metrics, imperfections) from your message
    2. Persist them to the knowledge graph
    3. Analyze the current state (imperfections, VFE)
    4. Return a grounded response with concrete next steps

    If LLM is enabled (LLM_ENABLED=true, OPENAI_API_KEY set),
    responses are natural and context-aware.
    If LLM is disabled, responses are structured summaries of graph state.
    """
    pipeline = get_chat_pipeline()
    try:
        result = await pipeline.run(
            message=req.message,
            session_id=req.session_id,
            job_id=req.job_id,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pipeline error: {e}")

    return ChatOut(
        session_id=result.session_id,
        assistant_message=result.assistant_message,
        intent=result.intent,
        entities_created=result.entities_created,
        entities_updated=result.entities_updated,
        imperfections=result.imperfections,
        vfe_current=result.vfe_current,
        top_blocker=result.top_blocker,
    )
