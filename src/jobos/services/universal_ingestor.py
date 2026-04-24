"""JobOS 4.0 — Universal Input Pipeline.

Single entry point that accepts any combination of text, URLs, and files,
auto-detects the input type, and produces a HierarchyResult + context.

Detection chain:
1. Files → CSV hierarchy? direct parse : extract text
2. URLs → fetch + extract text
3. Merged text → 5W1H context → SOP steps? extract : LLM hierarchy
4. Persist → return result
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from jobos.adapters.extraction.context_builder import (
    ContextSummary,
    build_context_from_text,
)
from jobos.adapters.extraction.csv_hierarchy_parser import (
    detect_hierarchy_csv,
    parse_hierarchy_csv,
)
from jobos.adapters.extraction.document_extractor import (
    SUPPORTED_EXTENSIONS,
    extract_from_bytes,
)
from jobos.kernel.hierarchy import HierarchyContext, HierarchyResult

logger = logging.getLogger(__name__)

_STEP_PATTERN = re.compile(
    r"(?:^\d+[.)]\s|^step\s+\d+|^[-*]\s+)",
    re.IGNORECASE | re.MULTILINE,
)


class IngestRequest(BaseModel):
    """Unified input request — any combination of fields."""
    text: str = ""
    url: str = ""
    urls: list[str] = Field(default_factory=list)
    files: list[tuple[bytes, str]] = Field(default_factory=list)
    domain: str = ""
    goal: str = ""

    model_config = {"arbitrary_types_allowed": True}


@dataclass
class IngestResult:
    """Unified output from the ingestion pipeline."""
    hierarchy: HierarchyResult | None = None
    hierarchy_raw: dict[str, Any] = field(default_factory=dict)
    context: ContextSummary | None = None
    entities_created: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    source_type: str = ""
    domain_detected: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hierarchy": (
                self.hierarchy_raw
                if self.hierarchy_raw
                else (
                    {
                        "id": self.hierarchy.id,
                        "domain": self.hierarchy.context.domain,
                        "jobs": [
                            {
                                "id": j.id,
                                "tier": j.tier.value if hasattr(j.tier, "value") else str(j.tier),
                                "statement": j.statement,
                                "category": j.category,
                                "rationale": j.rationale,
                                "metrics_hint": j.metrics_hint,
                                "executor_type": j.executor_type or "HUMAN",
                            }
                            for j in self.hierarchy.jobs
                        ],
                        "edges": [
                            {
                                "parent_id": e.parent_id,
                                "child_id": e.child_id,
                                "strength": e.strength,
                            }
                            for e in self.hierarchy.edges
                        ],
                        "summary": self.hierarchy.summary,
                    }
                    if self.hierarchy
                    else {}
                )
            ),
            "context": {
                "who": self.context.who if self.context else "",
                "why": self.context.why if self.context else "",
                "what": self.context.what if self.context else "",
                "where": self.context.where if self.context else "",
                "when": self.context.when if self.context else "",
                "how": self.context.how if self.context else "",
                "keywords": self.context.keywords if self.context else [],
                "job_hints": self.context.job_hints if self.context else [],
            },
            "entities_created": self.entities_created,
            "provenance": self.provenance,
            "source_type": self.source_type,
            "domain_detected": self.domain_detected,
            "warnings": self.warnings,
        }


class UniversalIngestor:
    """Orchestrates extraction → context → hierarchy from any input."""

    def __init__(
        self,
        hierarchy_service=None,
        sop_service=None,
        llm=None,
        graph=None,
    ) -> None:
        self._hierarchy_service = hierarchy_service
        self._sop_service = sop_service
        self._llm = llm
        self._graph = graph

    async def ingest(self, request: IngestRequest) -> IngestResult:
        """Main entry point — auto-detects input type and produces hierarchy."""
        result = IngestResult()
        provenance_sources: list[str] = []

        if not request.text and not request.url and not request.urls and not request.files:
            result.warnings.append("No input provided")
            return result

        # Step 1: Extract text from all sources
        texts, csv_result = await self._extract_from_sources(
            request, provenance_sources, result,
        )

        # If CSV parsing produced a hierarchy directly, return it
        if csv_result:
            result.hierarchy_raw = csv_result
            result.source_type = "csv_hierarchy"
            result.domain_detected = csv_result.get("domain", "")
            result.provenance = {"sources": provenance_sources}
            logger.info("CSV hierarchy detected: %d jobs", len(csv_result.get("jobs", [])))
            return result

        # Step 2: Merge all extracted text
        merged = self._merge_texts(texts)
        if not merged.strip():
            result.warnings.append("No usable text extracted from inputs")
            return result

        # Step 3: Build 5W1H context
        context = await build_context_from_text(merged, llm=self._llm)
        result.context = context

        # Step 4: Detect structure and generate hierarchy
        domain = request.domain or self._infer_domain(context)
        result.domain_detected = domain

        if self._looks_like_steps(merged):
            result.source_type = "sop_steps"
            raw = await self._generate_from_steps(merged, domain)
            result.hierarchy_raw = raw
        else:
            result.source_type = "text_to_hierarchy"
            hierarchy = await self._generate_hierarchy(
                domain=domain,
                goal=request.goal or context.why or "",
                keywords=context.keywords,
                text_context=merged[:500],
            )
            result.hierarchy = hierarchy

        result.provenance = {"sources": provenance_sources}
        logger.info(
            "Ingestion complete: source_type=%s, domain=%s",
            result.source_type, result.domain_detected,
        )
        return result

    async def _extract_from_sources(
        self,
        request: IngestRequest,
        provenance: list[str],
        result: IngestResult,
    ) -> tuple[list[str], dict | None]:
        """Extract text from files and URLs. Returns (texts, csv_result_or_None)."""
        texts: list[str] = []

        # Files
        for content, filename in request.files:
            provenance.append(f"file:{filename}")
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            # Check for CSV hierarchy first
            if ext == ".csv":
                try:
                    text = content.decode("utf-8", errors="replace")
                    if detect_hierarchy_csv(text):
                        csv_result = parse_hierarchy_csv(text)
                        if csv_result:
                            return texts, csv_result
                    texts.append(text)
                except Exception as e:
                    result.warnings.append(f"CSV parse failed for {filename}: {e}")
                continue

            if ext in SUPPORTED_EXTENSIONS:
                try:
                    extracted = extract_from_bytes(content, filename)
                    if extracted and extracted.text:
                        texts.append(extracted.text)
                except Exception as e:
                    result.warnings.append(f"Extraction failed for {filename}: {e}")
            else:
                result.warnings.append(f"Unsupported file format: {ext}")

        # URLs
        all_urls = list(request.urls)
        if request.url:
            all_urls.insert(0, request.url)

        for url in all_urls:
            provenance.append(f"url:{url}")
            try:
                from jobos.adapters.extraction.url_extractor import extract_from_url
                extracted = await extract_from_url(url)
                if extracted and extracted.text:
                    texts.append(extracted.text)
            except Exception as e:
                result.warnings.append(f"URL extraction failed for {url}: {e}")

        # Direct text
        if request.text:
            provenance.append("text:direct_input")
            texts.append(request.text)

        return texts, None

    def _merge_texts(self, texts: list[str]) -> str:
        """Merge multiple extracted texts, removing exact duplicates."""
        seen: set[str] = set()
        unique: list[str] = []
        for t in texts:
            normalized = t.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)
        return "\n\n---\n\n".join(unique)

    def _infer_domain(self, context: ContextSummary) -> str:
        """Infer domain from 5W1H context keywords."""
        if context.where:
            return context.where
        if context.keywords:
            return " ".join(context.keywords[:3])
        if context.what:
            return context.what[:50]
        return "general"

    def _looks_like_steps(self, text: str) -> bool:
        """Detect if text contains numbered/bulleted step lists."""
        matches = _STEP_PATTERN.findall(text)
        return len(matches) >= 3

    async def _generate_from_steps(self, text: str, domain: str) -> dict:
        """Route through SOP ingestion for step-structured text."""
        if self._sop_service:
            return await self._sop_service.ingest_from_text(text, domain)

        from jobos.services.sop_ingestion_service import SOPIngestionService
        svc = SOPIngestionService(llm=self._llm)
        return await svc.ingest_from_text(text, domain)

    async def _generate_hierarchy(
        self,
        domain: str,
        goal: str = "",
        keywords: list[str] | None = None,
        text_context: str = "",
    ) -> HierarchyResult | None:
        """Route through HierarchyService for text → hierarchy."""
        if not self._hierarchy_service:
            return None

        context = HierarchyContext(
            domain=domain,
            keywords=keywords or [],
            goal=goal,
            constraints=text_context,
        )
        return await self._hierarchy_service.generate(context)
