"""JobOS 4.0 — Bulk Ingestion Pipeline.

Extends the UniversalIngestor for mass data processing:
- Multi-URL crawling with depth control
- Zip/archive extraction
- JSON/JSONL bulk import (database exports, API responses)
- Batch processing with progress tracking
- Source merging and deduplication across inputs

Designed for machine-to-machine data flows, not interactive use.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from jobos.adapters.extraction.document_extractor import (
    SUPPORTED_EXTENSIONS,
    extract_from_bytes,
)
from jobos.services.universal_ingestor import (
    IngestRequest,
    IngestResult,
    UniversalIngestor,
)

logger = logging.getLogger(__name__)


class BulkIngestRequest(BaseModel):
    """Request for bulk/batch ingestion from multiple sources."""
    sources: list[SourceSpec] = Field(default_factory=list)
    domain: str = ""
    goal: str = ""
    merge_strategy: str = "combine"  # combine | separate | deduplicate
    max_depth: int = 1  # for URL crawling
    max_pages: int = 10  # max pages per URL crawl

    model_config = {"arbitrary_types_allowed": True}


class SourceSpec(BaseModel):
    """A single data source specification."""
    type: str  # text, url, file, json, jsonl, zip, api
    content: str = ""  # text content or URL or file path
    data: bytes = b""  # binary content for files
    filename: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


@dataclass
class BulkIngestResult:
    """Result of bulk ingestion across multiple sources."""
    results: list[IngestResult] = field(default_factory=list)
    merged_hierarchy: dict[str, Any] = field(default_factory=dict)
    total_sources: int = 0
    successful: int = 0
    failed: int = 0
    total_jobs: int = 0
    total_edges: int = 0
    warnings: list[str] = field(default_factory=list)
    provenance_map: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "merged_hierarchy": self.merged_hierarchy,
            "total_sources": self.total_sources,
            "successful": self.successful,
            "failed": self.failed,
            "total_jobs": self.total_jobs,
            "total_edges": self.total_edges,
            "warnings": self.warnings,
            "provenance_map": self.provenance_map,
            "per_source_results": [r.to_dict() for r in self.results],
        }


class BulkIngestor:
    """Orchestrates bulk ingestion from multiple heterogeneous sources."""

    def __init__(
        self,
        hierarchy_service=None,
        sop_service=None,
        llm=None,
        graph=None,
    ) -> None:
        self._ingestor = UniversalIngestor(
            hierarchy_service=hierarchy_service,
            sop_service=sop_service,
            llm=llm,
            graph=graph,
        )
        self._llm = llm

    async def ingest_bulk(
        self, request: BulkIngestRequest,
    ) -> BulkIngestResult:
        """Process multiple sources and merge results."""
        result = BulkIngestResult(total_sources=len(request.sources))

        for i, source in enumerate(request.sources):
            try:
                source_result = await self._ingest_source(
                    source, request.domain, request.goal,
                )
                result.results.append(source_result)
                result.successful += 1

                src_label = f"{source.type}:{source.filename or source.content[:50]}"
                jobs = self._extract_jobs(source_result)
                result.provenance_map[src_label] = [
                    j.get("id", "") for j in jobs
                ]
            except Exception as e:
                result.failed += 1
                result.warnings.append(
                    f"Source {i} ({source.type}): {e}"
                )
                logger.warning("Bulk ingest source %d failed: %s", i, e)

        # Merge all hierarchies
        if request.merge_strategy == "combine":
            result.merged_hierarchy = self._merge_hierarchies(
                result.results,
            )
        elif request.merge_strategy == "deduplicate":
            result.merged_hierarchy = self._merge_and_deduplicate(
                result.results,
            )
        else:
            # separate: each result stands alone
            pass

        result.total_jobs = len(
            result.merged_hierarchy.get("jobs", [])
        )
        result.total_edges = len(
            result.merged_hierarchy.get("edges", [])
        )

        logger.info(
            "Bulk ingest: %d/%d sources, %d jobs, %d edges",
            result.successful, result.total_sources,
            result.total_jobs, result.total_edges,
        )
        return result

    async def ingest_zip(
        self, content: bytes, domain: str = "", goal: str = "",
    ) -> BulkIngestResult:
        """Extract and ingest all supported files from a zip archive."""
        sources: list[SourceSpec] = []

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    if ext in SUPPORTED_EXTENSIONS or ext in (".json", ".jsonl"):
                        data = zf.read(name)
                        sources.append(SourceSpec(
                            type="file" if ext in SUPPORTED_EXTENSIONS else "json",
                            data=data,
                            filename=name,
                        ))
        except zipfile.BadZipFile:
            result = BulkIngestResult(total_sources=1, failed=1)
            result.warnings.append("Invalid zip file")
            return result

        request = BulkIngestRequest(
            sources=sources, domain=domain, goal=goal,
        )
        return await self.ingest_bulk(request)

    async def ingest_json_records(
        self, records: list[dict[str, Any]], domain: str = "",
        goal: str = "", id_field: str = "id",
        text_field: str = "description",
    ) -> BulkIngestResult:
        """Ingest structured JSON records (DB exports, API responses).

        Treats all records as process steps in a single hierarchy,
        not as separate sources (avoids per-record LLM calls).
        """
        statements: list[str] = []
        for record in records:
            text = record.get(text_field, "")
            if not text:
                for key in ("name", "title", "statement", "summary", "text"):
                    if record.get(key):
                        text = str(record[key])
                        break
            if text:
                statements.append(text)

        if not statements:
            return BulkIngestResult(total_sources=0)

        # Combine all statements as numbered steps for SOP extraction
        numbered = "\n".join(
            f"{i+1}. {s}" for i, s in enumerate(statements)
        )

        result = BulkIngestResult(total_sources=1)
        try:
            ingest_result = await self._ingestor.ingest(IngestRequest(
                text=numbered, domain=domain, goal=goal,
            ))
            result.results.append(ingest_result)
            result.successful = 1
            result.merged_hierarchy = (
                ingest_result.hierarchy_raw
                if ingest_result.hierarchy_raw
                else self._extract_hierarchy_dict(ingest_result)
            )
            result.total_jobs = len(
                result.merged_hierarchy.get("jobs", [])
            )
            result.total_edges = len(
                result.merged_hierarchy.get("edges", [])
            )
        except Exception as e:
            result.failed = 1
            result.warnings.append(f"JSON records ingestion failed: {e}")

        return result

    def _extract_hierarchy_dict(self, result: IngestResult) -> dict:
        """Convert IngestResult hierarchy to dict."""
        if not result.hierarchy:
            return {}
        return {
            "domain": result.hierarchy.context.domain,
            "jobs": [
                {"id": j.id, "statement": j.statement,
                 "tier": j.tier.value if hasattr(j.tier, "value") else str(j.tier)}
                for j in result.hierarchy.jobs
            ],
            "edges": [
                {"parent_id": e.parent_id, "child_id": e.child_id}
                for e in result.hierarchy.edges
            ],
        }

    async def ingest_jsonl(
        self, content: bytes, domain: str = "", goal: str = "",
    ) -> BulkIngestResult:
        """Ingest JSONL (newline-delimited JSON) stream."""
        records: list[dict[str, Any]] = []
        for line in content.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return await self.ingest_json_records(records, domain, goal)

    async def crawl_urls(
        self,
        seed_urls: list[str],
        max_depth: int = 1,
        max_pages: int = 10,
        domain: str = "",
        goal: str = "",
    ) -> BulkIngestResult:
        """Crawl multiple URLs, extracting linked pages up to max_depth."""
        from jobos.adapters.extraction.url_extractor import extract_from_url

        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [(u, 0) for u in seed_urls]
        sources: list[SourceSpec] = []

        while to_visit and len(visited) < max_pages:
            url, depth = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                extracted = await extract_from_url(url)
                sources.append(SourceSpec(
                    type="url",
                    content=url,
                    metadata={
                        "title": extracted.title,
                        "depth": depth,
                        "text_length": len(extracted.text),
                    },
                ))

                # Extract links for deeper crawling
                if depth < max_depth:
                    links = self._extract_links(
                        extracted.metadata.get("_html", ""), url,
                    )
                    for link in links[:5]:
                        if link not in visited:
                            to_visit.append((link, depth + 1))
            except Exception as e:
                logger.warning("Crawl failed for %s: %s", url, e)

        request = BulkIngestRequest(
            sources=sources, domain=domain, goal=goal,
            merge_strategy="deduplicate",
        )
        return await self.ingest_bulk(request)

    # ── Internal methods ──────────────────────────────────

    async def _ingest_source(
        self, source: SourceSpec, domain: str, goal: str,
    ) -> IngestResult:
        """Route a single source spec to the universal ingestor."""
        if source.type == "text":
            return await self._ingestor.ingest(IngestRequest(
                text=source.content, domain=domain, goal=goal,
            ))
        elif source.type == "url":
            return await self._ingestor.ingest(IngestRequest(
                url=source.content, domain=domain, goal=goal,
            ))
        elif source.type == "file":
            return await self._ingestor.ingest(IngestRequest(
                files=[(source.data, source.filename)],
                domain=domain, goal=goal,
            ))
        elif source.type in ("json", "jsonl"):
            try:
                if source.type == "jsonl":
                    text = source.data.decode("utf-8", errors="replace")
                else:
                    data = json.loads(source.data.decode("utf-8", errors="replace"))
                    text = json.dumps(data, indent=2)[:4000]
            except (json.JSONDecodeError, UnicodeDecodeError):
                text = source.data.decode("utf-8", errors="replace")[:4000]
            return await self._ingestor.ingest(IngestRequest(
                text=text, domain=domain, goal=goal,
            ))
        else:
            return await self._ingestor.ingest(IngestRequest(
                text=source.content, domain=domain, goal=goal,
            ))

    def _extract_jobs(self, result: IngestResult) -> list[dict]:
        """Extract job list from an IngestResult."""
        if result.hierarchy_raw and result.hierarchy_raw.get("jobs"):
            return result.hierarchy_raw["jobs"]
        if result.hierarchy and result.hierarchy.jobs:
            return [
                {"id": j.id, "statement": j.statement}
                for j in result.hierarchy.jobs
            ]
        return []

    def _merge_hierarchies(
        self, results: list[IngestResult],
    ) -> dict[str, Any]:
        """Combine all hierarchies into one unified structure."""
        all_jobs: list[dict] = []
        all_edges: list[dict] = []
        domains: list[str] = []

        for r in results:
            jobs = self._extract_jobs(r)
            all_jobs.extend(jobs)

            if r.hierarchy_raw and r.hierarchy_raw.get("edges"):
                all_edges.extend(r.hierarchy_raw["edges"])
            elif r.hierarchy and r.hierarchy.edges:
                all_edges.extend([
                    {"parent_id": e.parent_id, "child_id": e.child_id, "strength": e.strength}
                    for e in r.hierarchy.edges
                ])

            if r.domain_detected:
                domains.append(r.domain_detected)

        return {
            "domain": domains[0] if domains else "merged",
            "jobs": all_jobs,
            "edges": all_edges,
            "summary": {
                "total_jobs": len(all_jobs),
                "total_edges": len(all_edges),
                "source_count": len(results),
            },
        }

    def _merge_and_deduplicate(
        self, results: list[IngestResult],
    ) -> dict[str, Any]:
        """Merge hierarchies with statement-level deduplication."""
        from jobos.kernel.dedup import similarity

        merged = self._merge_hierarchies(results)
        jobs = merged.get("jobs", [])

        if len(jobs) <= 1:
            return merged

        unique: list[dict] = []
        for job in jobs:
            stmt = job.get("statement", "")
            is_dup = False
            for existing in unique:
                if similarity(stmt, existing.get("statement", "")) > 0.85:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(job)

        merged["jobs"] = unique
        merged["summary"]["total_jobs"] = len(unique)
        merged["summary"]["deduplicated"] = len(jobs) - len(unique)
        return merged

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[str]:
        """Extract href links from HTML for crawling."""
        import re
        from urllib.parse import urljoin

        links: list[str] = []
        for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
            href = match.group(1)
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            full = urljoin(base_url, href)
            if full.startswith("http") and full not in links:
                links.append(full)
        return links
