"""An external tool is still a tool.

MCP is where LASI talks to something it does not control, which is exactly the case where
"what ran, under whose authority" is hardest to reconstruct afterwards. These tests pin
that MCP gets no shortcut: same registry, same runner, same decision gate.
"""

import pytest
from services.contracts import ToolSpec
from services.integrations.mcp import (
    MCP_BACKEND,
    McpToolAdapter,
    McpToolDescriptor,
    McpUnavailableError,
    register_mcp_tool,
    tool_spec_from_descriptor,
)
from services.tools.errors import ToolNotFoundError
from services.tools.registry import ToolRegistry


class _StubClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response if response is not None else {"metrics": {"score": 1.0}}
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if self.error is not None:
            raise self.error
        return self.response


def _descriptor(**overrides) -> McpToolDescriptor:
    base = {"name": "summarize", "server_id": "docs", "description": "Summarise a document"}
    return McpToolDescriptor(**{**base, **overrides})


def test_a_discovered_tool_is_not_executable_by_default() -> None:
    """A server must not be able to describe itself into privileges."""
    spec = tool_spec_from_descriptor(_descriptor())

    assert spec.approval_status == "pending"
    # The runner refuses anything that is not production_ready.
    assert spec.capability_state == "experimental"


def test_an_mcp_tool_declares_a_non_local_backend() -> None:
    """Isolation profiles forbid network access; an MCP tool must not look local."""
    spec = tool_spec_from_descriptor(_descriptor())

    assert spec.supported_execution_backends == [MCP_BACKEND]
    assert spec.entrypoint == "mcp://docs/summarize"


def test_registration_requires_the_mcp_backend() -> None:
    registry = ToolRegistry()
    mislabelled = ToolSpec(
        tool_id="mcp.docs.summarize",
        name="summarize",
        version="1.0",
        supported_execution_backends=["local"],
    )

    with pytest.raises(ValueError, match="mcp"):
        register_mcp_tool(registry, _StubClient(), _descriptor(), spec=mislabelled)


def test_an_unregistered_mcp_tool_cannot_be_found() -> None:
    """There is no path to an MCP tool that bypasses the registry."""
    registry = ToolRegistry()

    with pytest.raises(ToolNotFoundError):
        registry.get("mcp.docs.summarize")


def test_a_registered_tool_is_reachable_through_the_ordinary_registry() -> None:
    registry = ToolRegistry()

    spec = register_mcp_tool(registry, _StubClient(), _descriptor())

    assert registry.get(spec.tool_id).spec.tool_id == "mcp.docs.summarize"


def test_the_adapter_forwards_parameters_and_returns_tool_output() -> None:
    from services.tools.runner import ToolContext

    client = _StubClient({"metrics": {"score": 0.9}, "output_refs": ["ref-1"]})
    adapter = McpToolAdapter(client, _descriptor())
    context = ToolContext(
        project_id="p",
        dataset_version_id="dv",
        tool_run_id="run-1",
        experiment_id=None,
        experiment_plan_id=None,
        input_refs=(),
        parameters={"document": "doc-1"},
    )

    output = adapter(context)

    assert client.calls == [("summarize", {"document": "doc-1"})]
    assert output.metrics == {"score": 0.9}
    assert output.output_refs == ["ref-1"]


def test_a_remote_failure_is_surfaced_not_swallowed() -> None:
    from services.tools.runner import ToolContext

    adapter = McpToolAdapter(_StubClient(error=TimeoutError("server gone")), _descriptor())
    context = ToolContext(
        project_id="p",
        dataset_version_id="dv",
        tool_run_id="run-1",
        experiment_id=None,
        experiment_plan_id=None,
        input_refs=(),
        parameters={},
    )

    with pytest.raises(McpUnavailableError, match="server gone"):
        adapter(context)


def test_a_malformed_remote_response_is_refused() -> None:
    from services.tools.runner import ToolContext

    adapter = McpToolAdapter(_StubClient(response="not an object"), _descriptor())
    context = ToolContext(
        project_id="p",
        dataset_version_id="dv",
        tool_run_id="run-1",
        experiment_id=None,
        experiment_plan_id=None,
        input_refs=(),
        parameters={},
    )

    with pytest.raises(McpUnavailableError, match="non-object"):
        adapter(context)
