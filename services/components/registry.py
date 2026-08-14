"""Registry for trusted, typed components; no dynamic imports or arbitrary code."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from services.contracts import ComponentSpec

ComponentHandler = Callable[..., object]


@dataclass(frozen=True)
class RegisteredComponent:
    spec: ComponentSpec
    config_model: type[BaseModel]
    handler: ComponentHandler
    source_hash: str | None = None


class ComponentRegistry:
    """Explicit process-local inventory of approved component implementations."""

    def __init__(
        self, *, allow_experimental: bool = False, experimental_project_id: str | None = None
    ) -> None:
        if allow_experimental and not experimental_project_id:
            raise ValueError("experimental registries must be scoped to one project")
        self._items: dict[str, RegisteredComponent] = {}
        self.allow_experimental = allow_experimental
        self.experimental_project_id = experimental_project_id

    def register(
        self,
        spec: ComponentSpec,
        config_model: type[BaseModel],
        handler: ComponentHandler,
        *,
        source_hash: str | None = None,
    ) -> None:
        if spec.component_id in self._items:
            raise ValueError(f"component already registered: {spec.component_id}")
        schema = config_model.model_json_schema()
        if spec.config_schema and spec.config_schema != schema:
            raise ValueError("component config schema does not match its configuration model")
        normalized = spec.model_copy(update={"config_schema": schema})
        self._items[spec.component_id] = RegisteredComponent(
            normalized, config_model, handler, source_hash
        )

    def get(self, component_id: str, expected_version: str | None = None) -> RegisteredComponent:
        try:
            item = self._items[component_id]
        except KeyError as exc:
            raise ValueError(f"component is not registered: {component_id}") from exc
        if expected_version is not None and item.spec.version != expected_version:
            raise ValueError(
                f"component {component_id} requires version {expected_version}, "
                f"registered version is {item.spec.version}"
            )
        allowed_lifecycles = {"approved"}
        if self.allow_experimental:
            allowed_lifecycles.add("experimental")
        if item.spec.lifecycle not in allowed_lifecycles:
            raise ValueError(f"component is not executable: {component_id} ({item.spec.lifecycle})")
        return item

    def validate_config(
        self, component_id: str, value: dict[str, Any], expected_version: str | None = None
    ) -> BaseModel:
        item = self.get(component_id, expected_version)
        return item.config_model.model_validate(value)

    def all(self) -> tuple[ComponentSpec, ...]:
        return tuple(item.spec for item in self._items.values())

    def compatible(
        self, *, modality: str, problem_type: str, backend: str = "local"
    ) -> tuple[ComponentSpec, ...]:
        return tuple(
            spec
            for spec in self.all()
            if (not spec.supported_modalities or modality in spec.supported_modalities)
            and (not spec.supported_problem_types or problem_type in spec.supported_problem_types)
            and backend in spec.supported_execution_backends
        )

    def describe(self, component_id: str, expected_version: str | None = None) -> ComponentSpec:
        """Return metadata and the generated JSON-schema contract without source inspection."""
        return self.get(component_id, expected_version).spec
