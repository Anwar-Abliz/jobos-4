"""JobOS 4.0 — LLM Port (optional AI integration).

Gated behind LLM_ENABLED config flag. Used for:
- Intent classification in the chat pipeline
- Entity extraction from natural language
- Structured JSON generation (hierarchy, experience, outcomes)
- Socratic inquiry for assumption testing (Phase 2+)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        """Generate a plain text completion. Returns the assistant message."""
        ...

    @abstractmethod
    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Generate a structured JSON completion. Returns parsed dict."""
        ...

    @abstractmethod
    async def check_connectivity(self) -> dict[str, Any]:
        """Health check. Returns status dict."""
        ...
