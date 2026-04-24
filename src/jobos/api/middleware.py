"""JobOS 4.0 — Correlation ID Middleware.

Adds a unique X-Correlation-ID header to every request/response for
distributed tracing.  Stores the ID in contextvars so logging can
include it automatically.
"""
from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return correlation_id_var.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Adds X-Correlation-ID to request/response cycle."""

    async def dispatch(self, request: Request, call_next) -> Response:
        cid = request.headers.get("x-correlation-id", "")
        if not cid:
            cid = uuid.uuid4().hex[:16]

        token = correlation_id_var.set(cid)
        try:
            response: Response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            correlation_id_var.reset(token)
