"""JobOS 4.0 — MCP (Model Context Protocol) Tool Models.

Based on the Anthropic MCP specification.  Phase 1 provides Pydantic
models for tool definitions, calls, and results, plus a static
catalog of JobOS-native tools.

Phase 2: MCP server exposing these tools over stdio/SSE transport.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """Schema for a single MCP tool."""
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolCall(BaseModel):
    """An invocation of an MCP tool."""
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str = ""


class MCPToolResult(BaseModel):
    """The result returned by an MCP tool."""
    call_id: str = ""
    content: Any = None
    is_error: bool = False
    error_message: str = ""


# ── Static Tool Catalog ─────────────────────────────────

JOBOS_TOOL_CATALOG: list[MCPToolDefinition] = [
    MCPToolDefinition(
        name="hierarchy.generate",
        description="Generate a 4-tier job hierarchy (T1-T4) for a given root job statement.",
        input_schema={
            "type": "object",
            "properties": {
                "statement": {"type": "string", "description": "Root job statement"},
                "context": {"type": "string", "description": "Optional context"},
            },
            "required": ["statement"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "root_id": {"type": "string"},
                "functional_spine": {"type": "object"},
            },
        },
    ),
    MCPToolDefinition(
        name="imperfection.rank",
        description="Rank imperfections for a job by VFE severity.",
        input_schema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job entity ID"},
            },
            "required": ["job_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "imperfections": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
        },
    ),
    MCPToolDefinition(
        name="switch.evaluate",
        description="Evaluate whether a hire should be switched based on metric bounds.",
        input_schema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "metrics": {"type": "object"},
                "bounds": {"type": "object"},
            },
            "required": ["job_id", "metrics"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["HIRE", "FIRE", "NONE"]},
                "reason": {"type": "string"},
            },
        },
    ),
]
