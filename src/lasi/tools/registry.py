"""The executable tool registry.

Registration is deliberately explicit: an entrypoint in a contract is metadata,
not permission to import and execute arbitrary code.
"""

from collections.abc import Callable
from dataclasses import dataclass

from lasi.contracts import ToolSpec

from .errors import ToolNotFoundError, ToolVersionError

ToolHandler = Callable[..., object]


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    """In-memory registry used by planners and execution backends."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.tool_id in self._tools:
            raise ValueError(f"tool already registered: {spec.tool_id}")
        self._tools[spec.tool_id] = RegisteredTool(spec=spec, handler=handler)

    def replace(self, spec: ToolSpec, handler: ToolHandler) -> None:
        """Replace a registration explicitly, useful for test/toolbox updates."""
        self._tools[spec.tool_id] = RegisteredTool(spec=spec, handler=handler)

    def get(self, tool_id: str, expected_version: str | None = None) -> RegisteredTool:
        try:
            registered = self._tools[tool_id]
        except KeyError as exc:
            raise ToolNotFoundError(f"tool is not registered: {tool_id}") from exc
        if expected_version is not None and registered.spec.version != expected_version:
            raise ToolVersionError(
                f"tool {tool_id} requires version {expected_version}, "
                f"registered version is {registered.spec.version}"
            )
        if registered.spec.deprecated:
            raise ToolVersionError(f"tool is deprecated: {tool_id}")
        return registered

    def check_compatibility(
        self,
        tool_id: str,
        *,
        modality: str | None = None,
        problem_type: str | None = None,
        execution_backend: str = "local",
        expected_version: str | None = None,
    ) -> ToolSpec:
        spec = self.get(tool_id, expected_version).spec
        if (
            modality is not None
            and spec.supported_modalities
            and modality not in spec.supported_modalities
        ):
            raise ValueError(f"tool {tool_id} does not support modality {modality}")
        if (
            problem_type is not None
            and spec.supported_problem_types
            and problem_type not in spec.supported_problem_types
        ):
            raise ValueError(f"tool {tool_id} does not support problem type {problem_type}")
        if execution_backend not in spec.supported_execution_backends:
            raise ValueError(f"tool {tool_id} does not support backend {execution_backend}")
        return spec

    def all(self) -> tuple[ToolSpec, ...]:
        return tuple(item.spec for item in self._tools.values())
