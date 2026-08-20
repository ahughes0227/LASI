"""Surface an external MCP tool as an ordinary registered tool.

An MCP server is a remote process LASI does not control.  Nothing about that justifies a
shortcut around the tool registry or the decision gate — if anything it argues the
opposite, since an external tool is the case where "what exactly ran, under whose
authority" is hardest to reconstruct after the fact.

So the adapter deliberately offers no way to call a tool directly.  It produces a handler
that the registry accepts and the runner executes, and the runner is what checks the
plan, the decision, the approval, the capability state, and the isolation profile.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import Field
from services.contracts import ToolSpec
from services.contracts.models import StrictModel
from services.tools.registry import ToolRegistry

#: MCP tools execute outside this process, so they are never a `local` backend.  The
#: distinction matters to isolation profiles, which forbid network access for benchmark
#: work: a tool declaring `mcp` cannot be silently treated as a local computation.
MCP_BACKEND = "mcp"


class McpUnavailableError(RuntimeError):
    """The MCP server could not be reached, or returned something unusable."""


@runtime_checkable
class McpClient(Protocol):
    """The narrow slice of MCP that LASI uses.

    Injected rather than constructed here so that the boundary can be tested without a
    server, and so no particular MCP SDK version is baked into the tool layer.
    """

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class McpToolDescriptor(StrictModel):
    """What an MCP server advertises about one tool.

    Untrusted input: it comes from an external process.  It is converted into a
    `ToolSpec` rather than used directly, so that a server cannot describe itself into
    privileges — approval status and capability state are set on this side.
    """

    name: str
    description: str | None = None
    server_id: str
    version: str = "1.0"
    supported_modalities: list[str] = Field(default_factory=list)
    supported_problem_types: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)


def tool_spec_from_descriptor(
    descriptor: McpToolDescriptor,
    *,
    approval_status: str = "pending",
    capability_state: str = "experimental",
) -> ToolSpec:
    """Convert an advertised MCP tool into a `ToolSpec`.

    Defaults are the cautious ones on purpose.  A newly discovered external tool is
    `pending` and `experimental`, and the runner refuses to execute anything that is not
    `production_ready`; promoting it is a governed act on this side of the boundary, not
    something the server can assert about itself.
    """
    return ToolSpec(
        tool_id=f"mcp.{descriptor.server_id}.{descriptor.name}",
        name=descriptor.name,
        version=descriptor.version,
        description=descriptor.description,
        supported_modalities=list(descriptor.supported_modalities),
        supported_problem_types=list(descriptor.supported_problem_types),
        supported_execution_backends=[MCP_BACKEND],
        expected_artifacts=list(descriptor.expected_artifacts),
        approval_status=approval_status,
        capability_state=capability_state,
        entrypoint=f"mcp://{descriptor.server_id}/{descriptor.name}",
    )


class McpToolAdapter:
    """A tool handler that forwards one call to an MCP server."""

    def __init__(self, client: McpClient, descriptor: McpToolDescriptor) -> None:
        self.client = client
        self.descriptor = descriptor

    def __call__(self, context: Any) -> Any:
        from services.tools.runner import ToolOutput

        try:
            response = self.client.call_tool(self.descriptor.name, dict(context.parameters))
        except Exception as exc:
            # A remote failure is evidence, not a crash: it is recorded as a failed tool
            # run so that the assignment can route around it.
            raise McpUnavailableError(
                f"MCP tool {self.descriptor.name!r} on {self.descriptor.server_id!r} failed: {exc}"
            ) from exc
        if not isinstance(response, dict):
            raise McpUnavailableError("MCP tool returned a non-object response")
        return ToolOutput(
            output_refs=list(response.get("output_refs", [])),
            artifact_refs=list(response.get("artifact_refs", [])),
            metrics=dict(response.get("metrics", {})),
            warnings=list(response.get("warnings", [])),
        )


def register_mcp_tool(
    registry: ToolRegistry,
    client: McpClient,
    descriptor: McpToolDescriptor,
    *,
    spec: ToolSpec | None = None,
) -> ToolSpec:
    """Register an MCP tool for execution through the ordinary runner.

    A caller may supply an already-governed `ToolSpec`; otherwise the cautious default
    from `tool_spec_from_descriptor` is used, which the runner will refuse to execute
    until it has been promoted.
    """
    resolved = spec or tool_spec_from_descriptor(descriptor)
    if MCP_BACKEND not in resolved.supported_execution_backends:
        raise ValueError("an MCP tool must declare the 'mcp' execution backend")
    registry.register(resolved, McpToolAdapter(client, descriptor))
    return resolved
