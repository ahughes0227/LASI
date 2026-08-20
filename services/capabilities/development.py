"""Plan and mechanically scaffold fixed-shell capability packages."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import yaml

from services.contracts import CapabilityBuildPlan, CapabilitySpec, Provenance
from services.scaffolds import ScaffoldService

from .registry import CapabilityRegistry
from .resolver import CapabilityResolver

if TYPE_CHECKING:
    from services.components.registry import ComponentRegistry


_PACKAGE_FILES = (
    "capability.yaml",
    "contract/input.schema.json",
    "contract/output.schema.json",
    "implementation/pipeline.yaml",
    "evaluation/eval.yaml",
    "provenance/resolution.yaml",
    "provenance/build-plan.yaml",
    "provenance/research-decisions.yaml",
    "README.md",
)


class CapabilityDevelopmentService:
    """Deterministic stages around the model-assisted research/build steps."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        component_registry: ComponentRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.component_registry = component_registry

    def plan(
        self, capability: CapabilitySpec, *, registration_scope: str = "shared_toolbox"
    ) -> CapabilityBuildPlan:
        resolution = CapabilityResolver(self.registry).resolve(capability)
        reused_components = self._matching_components(capability)
        missing = resolution.missing_requirements
        questions = [f"What is the best supported implementation for {item}?" for item in missing]
        files = list(_PACKAGE_FILES) if resolution.action in {"compose", "new"} else []
        files_to_modify: list[str] = []
        affected: list[str] = []
        if resolution.action == "extend":
            target = self.registry.get(resolution.selected_capability_ids[0])
            files_to_modify = [
                target.provenance.source_path or f"capabilities/{target.capability_id}"
            ]
            affected = [
                item.capability_id for item in self.registry.dependents(target.capability_id)
            ]
        return CapabilityBuildPlan(
            build_id=f"capability-build-{uuid4().hex}",
            capability=capability,
            resolution=resolution,
            registration_scope=registration_scope,
            reused_capability_ids=resolution.selected_capability_ids,
            reused_component_ids=reused_components,
            research_questions=questions,
            files_to_create=files,
            files_to_modify=files_to_modify,
            affected_capability_ids=affected,
            tests_required=["contract", "functional", "integration", "regression"],
            evaluation_requirements=[
                "declared input and output contracts",
                "no unrequested side effects",
                "known limitation coverage",
            ],
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[resolution.resolution_id]),
        )

    def scaffold(self, plan: CapabilityBuildPlan, root: str | Path) -> Path:
        if plan.resolution.action in {"reuse", "extend"}:
            raise ValueError(
                f"{plan.resolution.action} resolution does not authorize a new package"
            )
        base = Path(root).resolve()
        target = (base / plan.capability.capability_id).resolve()
        if target.parent != base:
            raise ValueError("capability package must remain under the requested root")
        if target.exists():
            raise FileExistsError(f"capability package already exists: {target}")
        # The shell comes from the governed template so that three package kinds
        # cannot drift apart; the build plan remains the authority for its contents.
        ScaffoldService().render(
            "capability_package",
            target,
            data={
                "package_title": plan.capability.name,
                "package_summary": plan.capability.purpose,
            },
        )
        self._write_yaml(target / "capability.yaml", plan.capability.model_dump(mode="json"))
        self._write_json(
            target / "contract/input.schema.json", _contract_schema(plan.capability.accepts)
        )
        self._write_json(
            target / "contract/output.schema.json", _contract_schema(plan.capability.produces)
        )
        self._write_yaml(
            target / "implementation/pipeline.yaml",
            {
                "capability_id": plan.capability.capability_id,
                "execution_kind": plan.capability.execution_kind,
                "capabilities": plan.reused_capability_ids,
                "components": plan.reused_component_ids,
                "custom_implementation": [],
            },
        )
        self._write_yaml(
            target / "evaluation/eval.yaml",
            {"requirements": plan.evaluation_requirements, "cases": []},
        )
        self._write_yaml(
            target / "provenance/resolution.yaml", plan.resolution.model_dump(mode="json")
        )
        self._write_yaml(target / "provenance/build-plan.yaml", plan.model_dump(mode="json"))
        self._write_yaml(target / "provenance/research-decisions.yaml", {"decisions": []})
        for suite in plan.tests_required:
            (target / "tests" / suite / "README.md").write_text(
                f"# {suite.title()} tests\n\nAdd executable evidence before registration.\n",
                encoding="utf-8",
            )
        return target

    def _matching_components(self, capability: CapabilitySpec) -> list[str]:
        if self.component_registry is None:
            return []
        requested = " ".join([capability.purpose, *capability.operations]).lower()
        matches: list[str] = []
        for component in self.component_registry.all():
            searchable = " ".join(
                [component.component_id, component.name, component.description or ""]
            ).lower()
            if any(word in searchable for word in requested.split() if len(word) > 3):
                matches.append(component.component_id)
        return sorted(matches)

    @staticmethod
    def _write_yaml(path: Path, value: object) -> None:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contract_schema(media_types: list[str]) -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {"artifacts": {"type": "array", "items": {"type": "string"}}},
        "required": ["artifacts"],
        "x-lasi-media-types": media_types,
    }
