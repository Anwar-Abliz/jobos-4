"""JobOS 4.0 — OpenAI LLM Adapter.

Implements LLMPort using OpenAI's chat completion API.
Supports both plain completions and structured JSON extraction
via function calling / response_format.

Gated behind LLM_ENABLED config flag.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from jobos.ports.llm_port import LLMPort

logger = logging.getLogger(__name__)

# Default model for all operations
DEFAULT_MODEL = "gpt-4.1-mini"


class OpenAIAdapter(LLMPort):
    """OpenAI-compatible LLM adapter.

    Works with any OpenAI-compatible API: OpenAI, Qwen (DashScope),
    DeepSeek, Ollama, vLLM, etc. Just set base_url accordingly.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, base_url: str = "") -> None:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**client_kwargs)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> str:
        """Generate a plain text completion."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI completion failed: %s", e)
            return ""

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Generate a structured JSON completion.

        Uses response_format=json_object to ensure valid JSON output.
        Falls back to regex extraction if json_object mode fails.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt + "\n\nRespond in valid JSON only."},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("OpenAI returned invalid JSON, attempting extraction")
            return self._extract_json(response.choices[0].message.content or "")
        except Exception as e:
            logger.error("OpenAI JSON completion failed: %s", e)
            return {}

    async def check_connectivity(self) -> dict[str, Any]:
        """Health check — attempt a minimal completion."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return {"enabled": True, "ok": True, "model": self._model}
        except Exception as e:
            return {"enabled": True, "ok": False, "error": str(e)}

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Try to extract JSON from text that may contain markdown fences."""
        import re
        # Try markdown code fence
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Try finding a JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}
