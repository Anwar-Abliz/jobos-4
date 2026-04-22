"""JobOS 4.0 — SAP Ingestion Port.

Abstract interface for SAP data ingestion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SAPIngestionPort(ABC):
    """Abstract interface for SAP data ingestion."""

    @abstractmethod
    async def ingest_process(self, template: dict) -> str:
        """Ingest a process template. Returns process entity ID."""
        ...

    @abstractmethod
    async def ingest_org_structure(self, structure: dict) -> str:
        """Ingest an org structure. Returns company code entity ID."""
        ...

    @abstractmethod
    async def get_process_context(self, process_id: str) -> dict[str, Any]:
        """Get full context for a process."""
        ...

    @abstractmethod
    async def detect_context_drift(self, process_id: str) -> dict[str, Any]:
        """Detect context drift for a process."""
        ...
