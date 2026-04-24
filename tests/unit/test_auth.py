"""Tests for API key authentication.

Covers:
- require_auth returns None when no API key configured
- Import check (actual HTTP testing requires ASGI test client)
"""
from __future__ import annotations

import os

import pytest

from jobos.api.auth import get_api_key_from_env, require_auth


class TestGetApiKeyFromEnv:
    def test_returns_empty_when_not_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("JOBOS_API_KEY", raising=False)
        assert get_api_key_from_env() == ""

    def test_returns_key_when_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("JOBOS_API_KEY", "secret-key-123")
        assert get_api_key_from_env() == "secret-key-123"


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_api_key_configured(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("JOBOS_API_KEY", raising=False)

        # Create a minimal fake request with no auth headers
        class FakeRequest:
            headers = {}
            query_params = {}

        result = await require_auth(FakeRequest())  # type: ignore[arg-type]
        assert result is None


class TestImportCheck:
    """Verify the module can be imported without side effects."""

    def test_module_imports(self):
        from jobos.api import auth
        assert hasattr(auth, "require_auth")
        assert hasattr(auth, "get_api_key_from_env")
