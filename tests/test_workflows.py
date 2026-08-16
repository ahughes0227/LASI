"""Conformance tests for JSON workflow packages."""

from pathlib import Path

import pytest
from services.contracts import WorkflowDefinition
from services.workflows import WorkflowCompiler, WorkflowRegistry
from services.workflows.validation import WorkflowValidationError, validate_workflow

ROOT = Path(__file__).resolve().parents[1]


def test_all_workflow_packages_load_and_have_checked_in_schema() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflows = registry.install_all()
    assert {item.workflow_id for item in workflows} == {
        "ticket_intake",
        "dataset_diagnostic",
        "dataset_update_validation",
        "sabbatical_review",
        "foundation_opportunity_review",
        "experiment_research_loop",
        "benchmark_challenge",
        "deployment_readiness",
        "dataset_improvement_governance",
        "knowledge_change_review",
        "capability_development",
        "component_development",
    }
    assert (ROOT / "_schemas" / "workflow.schema.json").is_file()


def test_compiler_does_not_emit_execution_without_persisted_authority() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("dataset_diagnostic")
    proposal = WorkflowCompiler().compile(
        workflow,
        project_id="project",
        assignment_id="assignment",
        observed_revision=1,
        completed_nodes={
            "intake",
            "validate",
            "characterize",
            "plan_experiments",
            "authorize_experiment_plan",
        },
        available_artifacts={"experiment_plan_ready"},
    )
    assert proposal.tasks == []


def test_compiler_emits_execution_only_with_plan_and_allowing_decision() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("dataset_diagnostic")
    proposal = WorkflowCompiler().compile(
        workflow,
        project_id="project",
        assignment_id="assignment",
        observed_revision=1,
        completed_nodes={
            "intake",
            "validate",
            "characterize",
            "plan_experiments",
            "authorize_experiment_plan",
        },
        available_artifacts={"experiment_plan_ready"},
        persisted_plan_ids={"experiment_plan"},
        allowing_decision_ids={"experiment_decision"},
    )
    assert [task.task_type for task in proposal.tasks] == ["experiment_execution"]
    assert proposal.tasks[0].experiment_plan_id == "experiment_plan"
    assert proposal.tasks[0].decision_id == "experiment_decision"


def test_validation_rejects_cycles() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("ticket_intake")
    cyclic = WorkflowDefinition.model_validate(
        workflow.model_copy(
            update={
                "nodes": [
                    workflow.nodes[0].model_copy(update={"dependencies": ["handoff"]}),
                    *workflow.nodes[1:],
                ]
            }
        )
    )
    with pytest.raises(WorkflowValidationError, match="cycle"):
        validate_workflow(
            cyclic,
            skills={"dataset-intake", "decision-review"},
            capabilities={"eda", "evaluation", "research"},
            prompts={("dataset_intake", "1.0"), ("decision_review", "1.0")},
            rubrics={("dataset_intake", "1.0"), ("decision_review", "1.0")},
            profiles={},
        )
