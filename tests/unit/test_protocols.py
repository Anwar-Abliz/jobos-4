"""Tests for A2A and MCP protocol models.

Covers:
- A2ATask, AgentCard, TaskState model creation
- MCPToolDefinition, MCPToolCall, MCPToolResult model creation
- JOBOS_TOOL_CATALOG is non-empty and all tools have names
"""
from __future__ import annotations

from jobos.protocols.a2a import A2ATask, AgentCard, TaskState
from jobos.protocols.mcp import (
    MCPToolCall,
    MCPToolDefinition,
    MCPToolResult,
    JOBOS_TOOL_CATALOG,
)


class TestA2AModels:
    def test_task_state_values(self):
        assert TaskState.SUBMITTED == "submitted"
        assert TaskState.WORKING == "working"
        assert TaskState.COMPLETED == "completed"
        assert TaskState.FAILED == "failed"
        assert TaskState.CANCELED == "canceled"
        assert TaskState.INPUT_REQUIRED == "input-required"

    def test_a2a_task_creation(self):
        task = A2ATask(id="t1", job_id="j1", method="hierarchy.generate")
        assert task.id == "t1"
        assert task.job_id == "j1"
        assert task.state == TaskState.SUBMITTED
        assert task.input_message == {}
        assert task.output_artifacts == []

    def test_a2a_task_state_transition(self):
        task = A2ATask(id="t1", job_id="j1", state=TaskState.WORKING)
        assert task.state == TaskState.WORKING

    def test_agent_card_creation(self):
        card = AgentCard(
            name="JobOS Hierarchy Agent",
            description="Generates job hierarchies",
            url="http://localhost:8000",
            capabilities=["hierarchy.generate", "imperfection.rank"],
        )
        assert card.name == "JobOS Hierarchy Agent"
        assert len(card.capabilities) == 2

    def test_agent_card_minimal(self):
        card = AgentCard(name="test")
        assert card.name == "test"
        assert card.url == ""
        assert card.capabilities == []


class TestMCPModels:
    def test_tool_definition_creation(self):
        tool = MCPToolDefinition(
            name="test.tool",
            description="A test tool",
            input_schema={"type": "object"},
        )
        assert tool.name == "test.tool"
        assert tool.output_schema == {}

    def test_tool_call_creation(self):
        call = MCPToolCall(
            tool_name="hierarchy.generate",
            arguments={"statement": "Define scope"},
            call_id="c1",
        )
        assert call.tool_name == "hierarchy.generate"
        assert call.arguments["statement"] == "Define scope"

    def test_tool_result_success(self):
        result = MCPToolResult(
            call_id="c1",
            content={"root_id": "r1"},
            is_error=False,
        )
        assert result.is_error is False
        assert result.content["root_id"] == "r1"

    def test_tool_result_error(self):
        result = MCPToolResult(
            call_id="c1",
            is_error=True,
            error_message="Job not found",
        )
        assert result.is_error is True
        assert "not found" in result.error_message


class TestToolCatalog:
    def test_catalog_is_non_empty(self):
        assert len(JOBOS_TOOL_CATALOG) > 0

    def test_catalog_has_3_tools(self):
        assert len(JOBOS_TOOL_CATALOG) == 3

    def test_all_tools_have_names(self):
        for tool in JOBOS_TOOL_CATALOG:
            assert tool.name, f"Tool missing name: {tool}"
            assert isinstance(tool, MCPToolDefinition)

    def test_expected_tool_names(self):
        names = {t.name for t in JOBOS_TOOL_CATALOG}
        assert "hierarchy.generate" in names
        assert "imperfection.rank" in names
        assert "switch.evaluate" in names
