"""JobOS 4.0 — LLM Port (optional AI integration).

Gated behind LLM_ENABLED config flag. Used for:
- Intent classification in the chat pipeline
- Entity extraction from natural language
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
        """Generate a completion. Returns the assistant message."""
        ...

    @abstractmethod
    async def check_connectivity(self) -> dict[str, Any]:
        """Health check. Returns status dict."""
        ...
