"""JobOS 4.0 — API Key Authentication.

Provides optional API key authentication.  When JOBOS_API_KEY is set
in the environment, all API requests must include it.  When not set,
authentication is disabled (backward compatible).
"""
from __future__ import annotations

import os

from fastapi import HTTPException, Request


def get_api_key_from_env() -> str:
    """Read API key from environment. Empty string = auth disabled."""
    return os.environ.get("JOBOS_API_KEY", "")


async def require_auth(request: Request) -> str | None:
    """FastAPI dependency that checks for API key.

    If JOBOS_API_KEY is not set, authentication is disabled and this
    returns None.  If set, checks X-API-Key header or api_key query param.
    """
    expected = get_api_key_from_env()
    if not expected:
        return None

    provided = request.headers.get("x-api-key", "")
    if not provided:
        provided = request.query_params.get("api_key", "")

    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return provided
