"""Focused tests for the Wave 3 experiment services."""

from datetime import date

import pytest
from services.contracts import DecisionRecord, ExperimentPlan, ToolRunResult
from services.experiments import (
    DuplicateExperimentDetector,
    assemble_diagnostic_packet,
    build_reproducibility_record,
    compile_plan,
    require_allowed_decision,
)


def recommendation(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "project_id": "project-1",
        "dataset_version": "dataset:v1",
        "hypothesis": "baseline establishes the evidence floor",
        "experiment_type": "baseline_probe",
    }
    value.update(overrides)
    return value


def test_mvp_compilation_is_deterministic_and_contract_valid() -> None:
    first = compile_plan(recommendation())
    second = compile_plan(recommendation())

    assert first.plan.model_dump() == second.plan.model_dump()
    assert first.plan.experiment_plan_id.startswith("plan-")
    assert first.plan.planned_tool_runs[0].tool_id == "train_baseline_model"
    ExperimentPlan.model_validate(first.plan.model_dump())


def test_compiler_does_not_turn_approved_remote_compute_into_human_approval() -> None:
    result = compile_plan(
        recommendation(experiment_type="learning_curve", execution_backend="remote")
    )

    assert result.plan.approval_required is False
    assert result.plan.decision_record_required is True
    assert result.required_approvals == ()
    assert result.blocked_reasons == ("remote execution requires a remote_host_profile",)


def test_compiler_rejects_non_mvp_type() -> None:
    with pytest.raises(ValueError, match="unsupported MVP"):
        compile_plan(recommendation(experiment_type="ablation"))


def test_reproducibility_hashes_are_stable() -> None:
    plan = compile_plan(recommendation()).plan
    first = build_reproducibility_record(
        plan,
        manifest={"files": ["a"]},
        config={"seed": 7},
        tool_versions={"train_baseline_model": "1.0"},
        random_seed=7,
    )
    second = build_reproducibility_record(
        plan,
        manifest={"files": ["a"]},
        config={"seed": 7},
        tool_versions={"train_baseline_model": "1.0"},
        random_seed=7,
    )
    assert first == second
    assert first.manifest_hash
    assert first.config_hash


def test_duplicate_detector_is_an_interface_not_a_policy_decision() -> None:
    plan = compile_plan(recommendation()).plan
    match = DuplicateExperimentDetector().find_duplicate(plan, [("exp-1", plan, "succeeded")])

    assert match is not None
    assert match.experiment_id == "exp-1"
    assert DuplicateExperimentDetector().find_duplicate(plan, []) is None


def test_diagnostic_packet_assembles_history_and_deduplicates_artifacts() -> None:
    result = ToolRunResult(
        tool_run_id="run-1",
        project_id="project-1",
        experiment_plan_id="plan-1",
        dataset_version_id="dataset:v1",
        tool_id="train_baseline_model",
        tool_version="1.0",
        execution_backend="local",
        status="succeeded",
        artifact_refs=["metrics.json", "metrics.json"],
    )
    packet = assemble_diagnostic_packet(
        diagnostic_packet_id="packet-1",
        project_id="project-1",
        problem_type="classification",
        dataset_version_id="dataset:v1",
        privacy_mode="local_only",
        tool_results=[result],
        artifact_refs=["metrics.json", "errors.json"],
    )

    assert packet.experiment_history == ["plan-1"]
    assert packet.artifact_refs == ["metrics.json", "errors.json"]


def test_execution_guard_requires_matching_allowed_decision() -> None:
    plan = compile_plan(recommendation()).plan
    decision = DecisionRecord(
        decision_id="decision-1",
        project_id="project-1",
        experiment_plan_id=plan.experiment_plan_id,
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="within MVP scope",
    )
    require_allowed_decision(plan, decision)

    blocked = decision.model_copy(update={"decision": "block", "allowed": False})
    with pytest.raises(PermissionError):
        require_allowed_decision(plan, blocked)


def test_approval_guard_requires_approver() -> None:
    plan = compile_plan(recommendation()).plan
    decision = DecisionRecord(
        decision_id="decision-1",
        project_id=plan.project_id,
        experiment_plan_id=plan.experiment_plan_id,
        risk_level="medium",
        decision="allow",
        allowed=True,
        approval_required=True,
        approval_date=date.today(),
        rationale="approval pending",
    )
    with pytest.raises(PermissionError, match="approval"):
        require_allowed_decision(plan, decision)


def test_plan_approval_requirement_is_enforced_by_execution_guard() -> None:
    plan = compile_plan(recommendation(approval_required=True)).plan
    decision = DecisionRecord(
        decision_id="decision-1",
        project_id=plan.project_id,
        experiment_plan_id=plan.experiment_plan_id,
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="approval was omitted",
    )

    with pytest.raises(PermissionError, match="approval"):
        require_allowed_decision(plan, decision)
