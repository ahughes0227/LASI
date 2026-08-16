from pathlib import Path

import pytest
from services.domain import DomainEffect, DomainPredicate, PredicateOperator
from services.planner import DomainGoal, DomainPlan, PlannedCapabilityStep
from services.workflows import (
    DomainWorkflowBridge,
    WorkflowDevelopmentService,
    WorkflowPackageValidator,
    WorkflowRegistry,
)

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = DomainWorkflowBridge(ROOT / "system/domain_workflow_bindings.yaml")


def _predicate(subject: str, name: str, value: str = "ready") -> DomainPredicate:
    return DomainPredicate(
        subject=subject,
        predicate=name,
        operator=PredicateOperator.EQUALS,
        value=value,
    )


def _plan(
    *steps: PlannedCapabilityStep, desired: list[DomainPredicate] | None = None
) -> DomainPlan:
    desired = desired or [_predicate("project", "ready")]
    return DomainPlan(
        plan_id="domain-plan-test",
        goal=DomainGoal(
            goal_id="goal-test",
            project_id="project-test",
            description="Reach the requested domain state",
            desired_state=desired,
        ),
        observed_revision=7,
        status="planned",
        steps=list(steps),
        unresolved_predicate_indexes=list(range(len(desired))),
    )


def _step(capability: str, predicate: str, *, required: list[DomainPredicate] | None = None):
    return PlannedCapabilityStep(
        step_id=f"step-{capability}",
        capability_id=capability,
        required_predicates=required or [],
        expected_effects=[DomainEffect(operation="assert", subject="project", predicate=predicate)],
        side_effect_class="read",
    )


def test_bridge_translates_steps_in_dependency_order() -> None:
    workflow = BRIDGE.build_definition(
        _plan(_step("eda", "profile_ready"), _step("research", "plan_ready")),
        workflow_id="domain-flow",
    )
    assert [node.node_id for node in workflow.nodes] == ["step_00_eda", "step_01_research"]
    assert workflow.nodes[1].dependencies == ["step_00_eda"]
    assert [node.priority for node in workflow.nodes] == [0, 1]


def test_bridge_uses_existing_versioned_bindings() -> None:
    workflow = BRIDGE.build_definition(_plan(_step("eda", "ready")), workflow_id="domain-flow")
    node = workflow.nodes[0]
    assert node.task_type == "domain_eda"
    assert node.skill == "dataset-characterization"
    assert node.prompt.prompt_id == "dataset_characterization"
    assert node.prompt.version == "1.0"
    assert node.rubric.rubric_id == "dataset_intake"


def test_bridge_maps_effects_to_typed_artifacts() -> None:
    workflow = BRIDGE.build_definition(
        _plan(_step("eda", "profile.ready"), desired=[_predicate("project", "profile.ready")]),
        workflow_id="domain-flow",
    )
    assert workflow.nodes[0].writes[0].artifact_id == "domain_effect_00_profile_ready"
    assert workflow.nodes[0].writes[0].artifact_type == "domain/fact"
    assert workflow.outputs == ["domain_predicate_project_profile_ready"]


def test_bridge_rejects_blocked_or_incomplete_plan() -> None:
    for status in ("blocked", "incomplete"):
        plan = _plan(_step("eda", "ready")).model_copy(update={"status": status})
        with pytest.raises(ValueError, match="planned or satisfied"):
            BRIDGE.build_definition(plan, workflow_id="domain-flow")


def test_bridge_rejects_execution_without_plan_and_decision_artifacts() -> None:
    with pytest.raises(ValueError, match="experiment_decision|experiment_plan"):
        BRIDGE.build_definition(_plan(_step("modeling", "model_ready")), workflow_id="domain-flow")


def test_bridge_metadata_preserves_plan_provenance() -> None:
    plan = _plan(_step("eda", "ready"))
    plan = plan.model_copy(update={"policy_decisions": [], "unresolved_predicate_indexes": [0]})
    workflow = BRIDGE.build_definition(plan, workflow_id="domain-flow")
    assert workflow.metadata == {
        "domain_plan_id": "domain-plan-test",
        "observed_revision": 7,
        "policy_decision_count": 0,
        "unresolved_predicate_count": 1,
    }


def test_generated_definition_passes_graph_and_binding_validation(tmp_path: Path) -> None:
    plan = _plan(
        _step("research", "experiment_plan"),
        _step(
            "evaluation",
            "experiment_decision",
            required=[_predicate("project", "experiment_plan")],
        ),
        _step(
            "modeling",
            "model_ready",
            required=[_predicate("project", "experiment_decision")],
        ),
    )
    workflow = BRIDGE.build_definition(plan, workflow_id="generated-domain-flow")
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    build_plan = WorkflowDevelopmentService(registry).plan(workflow)
    package = WorkflowDevelopmentService(registry).scaffold(build_plan, tmp_path / "workflows")
    validation = WorkflowPackageValidator(ROOT).validate(package)
    assert validation.checks["graph_and_bindings_valid"]
    assert not validation.checks["tests_present"]
    assert not validation.checks["evaluation_cases_present"]
    assert not validation.checks["research_gaps_resolved"]


def test_generated_package_remains_uninstalled_and_unapproved(tmp_path: Path) -> None:
    workflow = BRIDGE.build_definition(_plan(_step("eda", "ready")), workflow_id="draft-flow")
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    build_plan = WorkflowDevelopmentService(registry).plan(workflow)
    package = WorkflowDevelopmentService(registry).scaffold(build_plan, tmp_path / "workflows")
    assert package.parent == (tmp_path / "workflows").resolve()
    assert not (ROOT / "_workflows" / "draft-flow").exists()
    assert not (package / "provenance/registration-proposal.json").exists()
