"""Plan and mechanically scaffold fixed-shell component packages."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import yaml

from services.contracts import ComponentBuildPlan, ComponentPort, ComponentSpec, Provenance

from .registry import ComponentRegistry
from .resolver import ComponentResolver

if TYPE_CHECKING:
    from services.planner import PlannerCatalog

_PACKAGE_FILES = (
    "component.yaml",
    "contract/config.schema.json",
    "contract/input.schema.json",
    "contract/output.schema.json",
    "implementation/runtime.yaml",
    "evaluation/eval.yaml",
    "provenance/resolution.yaml",
    "provenance/build-plan.yaml",
    "provenance/research-decisions.yaml",
    "README.md",
)


class ComponentDevelopmentService:
    def __init__(self, registry: ComponentRegistry, catalog: PlannerCatalog) -> None:
        self.registry = registry
        self.catalog = catalog

    def plan(self, component: ComponentSpec) -> ComponentBuildPlan:
        resolution = ComponentResolver(self.catalog, self.registry).resolve(component)
        files = list(_PACKAGE_FILES) if resolution.action == "new" else []
        files_to_modify = []
        if resolution.action == "extend" and resolution.selected_component_ids:
            existing = self.registry.describe(resolution.selected_component_ids[0])
            files_to_modify = [existing.provenance.source_path or "components/registered"]
        questions = [
            f"What is the minimum supported implementation for {item}?"
            for item in resolution.missing_requirements
        ]
        return ComponentBuildPlan(
            build_id=f"component-build-{uuid4().hex}",
            component=component,
            resolution=resolution,
            research_questions=questions,
            files_to_create=files,
            files_to_modify=files_to_modify,
            affected_capability_ids=resolution.affected_capability_ids,
            affected_workflow_ids=resolution.affected_workflow_ids,
            tests_required=["contract", "functional", "integration", "regression"],
            evaluation_requirements=[
                "declared input and output contracts",
                "one stable responsibility",
                "no operation selector in configuration",
                "declared operational requirements",
            ],
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[resolution.resolution_id]),
        )

    def scaffold(self, plan: ComponentBuildPlan, root: str | Path) -> Path:
        if plan.resolution.action != "new":
            raise ValueError(
                f"{plan.resolution.action} resolution does not authorize a new package"
            )
        base = Path(root).resolve()
        target = (base / plan.component.component_id).resolve()
        if target.parent != base:
            raise ValueError("component package must remain under the requested root")
        if target.exists():
            raise FileExistsError(f"component package already exists: {target}")
        for directory in (
            "contract",
            "implementation/src",
            "tests/contract",
            "tests/functional",
            "tests/integration",
            "tests/regression",
            "tests/fixtures",
            "evaluation",
            "provenance",
        ):
            (target / directory).mkdir(parents=True, exist_ok=True)
        self._write_yaml(target / "component.yaml", plan.component.model_dump(mode="json"))
        self._write_json(
            target / "contract/config.schema.json",
            plan.component.config_schema
            or {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
            },
        )
        self._write_json(
            target / "contract/input.schema.json", _ports_schema(plan.component.inputs)
        )
        self._write_json(
            target / "contract/output.schema.json", _ports_schema(plan.component.outputs)
        )
        self._write_yaml(
            target / "implementation/runtime.yaml",
            plan.component.runtime.model_dump(mode="json"),
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
        (target / "README.md").write_text(
            f"# {plan.component.name}\n\n"
            f"{plan.component.description or plan.component.responsibility or ''}\n\n"
            "This package is a draft until validation and governed registration succeed.\n",
            encoding="utf-8",
        )
        for suite in plan.tests_required:
            (target / "tests" / suite / "README.md").write_text(
                f"# {suite.title()} tests\n\nAdd executable evidence before registration.\n",
                encoding="utf-8",
            )
        return target

    @staticmethod
    def _write_yaml(path: Path, value: object) -> None:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ports_schema(ports: Sequence[ComponentPort]) -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {port.name: {"type": "string"} for port in ports},
        "required": [port.name for port in ports if port.required],
    }
