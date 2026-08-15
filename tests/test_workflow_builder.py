"""Conformance tests for the governed workflow builder capability."""

from pathlib import Path

from services.workflows import (
    WorkflowDevelopmentService,
    WorkflowPackageValidator,
    WorkflowRegistry,
    WorkflowResolver,
)

ROOT = Path(__file__).resolve().parents[1]


def _registry() -> WorkflowRegistry:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    registry.install_all()
    return registry


def test_workflow_builder_reuses_existing_contract() -> None:
    registry = _registry()
    workflow = registry.get("ticket_intake")
    resolution = WorkflowResolver(registry).resolve(workflow)
    assert resolution.action == "reuse"
    assert resolution.selected_workflow_ids == ["ticket_intake"]


def test_workflow_builder_new_request_gets_frozen_plan_and_fixed_shell(tmp_path: Path) -> None:
    registry = _registry()
    source = registry.get("ticket_intake")
    requested = source.model_copy(
        update={
            "workflow_id": "novel_workflow",
            "goal": "A genuinely new workflow primitive",
            "nodes": [
                source.nodes[0].model_copy(update={"task_type": "novel_task"}),
                *source.nodes[1:],
            ],
        }
    )
    plan = WorkflowDevelopmentService(registry).plan(requested)
    assert plan.resolution.action == "new"
    package = WorkflowDevelopmentService(registry).scaffold(plan, tmp_path / "workflows")
    assert (package / "workflow.json").is_file()
    assert (package / "provenance/build-plan.json").is_file()
    validation = WorkflowPackageValidator(ROOT).validate(package)
    assert not validation.passed
    assert not validation.checks["tests_present"]
    assert not validation.checks["evaluation_cases_present"]


def test_workflow_builder_does_not_scaffold_extension_as_duplicate(tmp_path: Path) -> None:
    registry = _registry()
    source = registry.get("ticket_intake")
    requested = source.model_copy(update={"version": "2.0"})
    plan = WorkflowDevelopmentService(registry).plan(requested)
    assert plan.resolution.action == "extend"
    try:
        WorkflowDevelopmentService(registry).scaffold(plan, tmp_path / "workflows")
    except ValueError as exc:
        assert "extend" in str(exc)
    else:
        raise AssertionError("extension resolution must not scaffold a duplicate package")
