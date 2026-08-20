"""Governed workflow package planning and fixed-shell scaffolding."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from services.contracts import (
    Provenance,
    WorkflowBuildPlan,
    WorkflowDefinition,
)
from services.scaffolds import ScaffoldService

from .registry import WorkflowRegistry
from .resolver import WorkflowResolver

_PACKAGE_FILES = (
    "workflow.json",
    "evaluation/eval.json",
    "provenance/resolution.json",
    "provenance/build-plan.json",
    "provenance/research-decisions.json",
    "README.md",
)


class WorkflowDevelopmentService:
    """Deterministic stages around workflow design and validation work."""

    def __init__(self, registry: WorkflowRegistry) -> None:
        self.registry = registry

    def plan(
        self, workflow: WorkflowDefinition, *, registration_scope: str = "installed_workflow"
    ) -> WorkflowBuildPlan:
        resolution = WorkflowResolver(self.registry).resolve(workflow)
        questions = [
            f"What is the minimum safe implementation for {item}?"
            for item in resolution.missing_requirements
        ]
        files = list(_PACKAGE_FILES) if resolution.action in {"compose", "new"} else []
        files_to_modify: list[str] = []
        affected: list[str] = []
        if resolution.action == "extend":
            existing = self.registry.get(resolution.selected_workflow_ids[0])
            files_to_modify = [f"_workflows/{existing.workflow_id}/workflow.json"]
        return WorkflowBuildPlan(
            build_id=f"workflow-build-{uuid4().hex}",
            workflow=workflow,
            resolution=resolution,
            registration_scope=registration_scope,
            research_questions=questions,
            files_to_create=files,
            files_to_modify=files_to_modify,
            affected_workflow_ids=affected,
            tests_required=["contract", "graph", "integration", "regression"],
            evaluation_requirements=[
                "all references resolve",
                "graph has no cycles or dangling dependencies",
                "execution remains decision-gated",
                "optional and blocked paths record reasons",
            ],
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[resolution.resolution_id]),
        )

    def scaffold(self, plan: WorkflowBuildPlan, root: str | Path) -> Path:
        if plan.resolution.action in {"reuse", "extend"}:
            raise ValueError(
                f"{plan.resolution.action} resolution does not authorize a new package"
            )
        base = Path(root).resolve()
        target = (base / plan.workflow.workflow_id).resolve()
        if target.parent != base:
            raise ValueError("workflow package must remain under the requested root")
        if target.exists():
            raise FileExistsError(f"workflow package already exists: {target}")
        # The shell comes from the governed template so that three package kinds
        # cannot drift apart; the build plan remains the authority for its contents.
        ScaffoldService().render(
            "workflow_package",
            target,
            data={
                "package_title": plan.workflow.workflow_id,
                "package_summary": plan.workflow.goal,
            },
        )
        self._write_json(target / "workflow.json", plan.workflow.model_dump(mode="json"))
        self._write_json(
            target / "evaluation/eval.json",
            {"requirements": plan.evaluation_requirements, "cases": []},
        )
        self._write_json(
            target / "provenance/resolution.json", plan.resolution.model_dump(mode="json")
        )
        self._write_json(target / "provenance/build-plan.json", plan.model_dump(mode="json"))
        self._write_json(target / "provenance/research-decisions.json", {"decisions": []})
        for suite in plan.tests_required:
            (target / "tests" / suite / "README.md").write_text(
                f"# {suite.title()} tests\n\nAdd executable evidence before installation.\n",
                encoding="utf-8",
            )
        return target

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
