"""JobOS 4.0 — A2A (Agent-to-Agent) Protocol Models.

Based on the Google A2A protocol specification.  Phase 1 provides
Pydantic models for task lifecycle management between JobOS agents.

Phase 2: HTTP client/server implementing the A2A JSON-RPC transport.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskState(str, Enum):
    """A2A task lifecycle states."""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class A2ATask(BaseModel):
    """An inter-agent task delegated via the A2A protocol.

    Maps to JobOS hiring: a Job (hirer) delegates work to an
    external agent (hiree) via a structured task envelope.
    """
    id: str
    job_id: str
    hiree_agent_url: str = ""
    method: str = ""
    state: TaskState = TaskState.SUBMITTED
    input_message: dict[str, Any] = Field(default_factory=dict)
    output_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class AgentCard(BaseModel):
    """Describes a remote agent's capabilities (A2A Agent Card).

    Used for agent discovery: which agents can be hired for which jobs.
    """
    name: str
    description: str = ""
    url: str = ""
    capabilities: list[str] = Field(default_factory=list)
