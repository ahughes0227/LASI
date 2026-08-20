"""Adversarial regressions for LASI's authority, durability, and reporting boundaries."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from services.admin import open_admin_service
from services.contracts import (
    AgentResult,
    CriterionResult,
    DecisionRecord,
    ExperimentPlan,
    ResearchLoopPolicy,
    StaticReportData,
    ToolSpec,
)
from services.experiments import experiment_plan_content_hash
from services.runtime import TaskRuntimeError, TaskRuntimeService
from services.tools import LocalToolRunner, ToolOutput, ToolRegistry

_SECTION_NAMES = (
    "executive_summary",
    "current_decision",
    "dataset_summary",
    "dataset_characterization",
    "eda_findings",
    "surprising_findings",
    "proposed_approaches",
    "experiment_summary",
    "experiments_tried",
    "results_and_interpretation",
    "model_comparison",
    "performance_gap_diagnosis",
    "learning_curves",
    "error_analysis",
    "cluster_or_latent_analysis",
    "scientist_review",
    "scientific_criticism",
    "decision_record",
    "knowledge_context",
    "recommendation",
    "project_outcome",
    "token_telemetry",
    "appendix",
)


def _plan(*, parameters: dict[str, object] | None = None) -> ExperimentPlan:
    tool_run: dict[str, object] = {"tool_id": "probe"}
    if parameters is not None:
        tool_run["parameters"] = parameters
    return ExperimentPlan(
        experiment_plan_id="plan-authorized",
        project_id="project-1",
        dataset_version="dataset:v1",
        hypothesis="The bounded probe produces discriminating evidence.",
        reason_for_experiment="Falsify an authority-boundary claim.",
        experiment_type="baseline_probe",
        planned_tool_runs=[tool_run],
        execution_backend="local",
        expected_signal="A bounded result is produced.",
        success_criteria="The declared probe completes.",
        failure_criteria="The declared probe fails.",
    )


def _decision(plan: ExperimentPlan) -> DecisionRecord:
    return DecisionRecord(
        decision_id="decision-authorized",
        project_id="project-1",
        experiment_plan_id="plan-authorized",
        experiment_plan_hash=experiment_plan_content_hash(plan),
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="The original immutable plan was authorized.",
    )


def _runner(observed: list[dict[str, object]]) -> LocalToolRunner:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(tool_id="probe", name="Bounded probe", version="1"),
        lambda context: observed.append(context.parameters) or ToolOutput(),
    )
    return LocalToolRunner(registry)


def _completed_planning_result(task_id: str, attempt_id: str) -> AgentResult:
    return AgentResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status="completed",
        summary="The objective is satisfied by existing evidence.",
        criterion_results=[
            CriterionResult(
                criterion_id="separate_observation_inference",
                status="satisfied",
                evidence_refs=["sql:evidence:observation"],
            ),
            CriterionResult(
                criterion_id="smallest_discriminating_next_step",
                status="satisfied",
                evidence_refs=["sql:evidence:next-step"],
            ),
        ],
        recommended_assignment_status="complete",
    )


def _loop_policy() -> ResearchLoopPolicy:
    return ResearchLoopPolicy(objective_metric="evidence_quality", objective_direction="maximize")


def _report_payload(section: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "report_id": "report-falsification",
        "report_header": {"title": "Falsification report", "project_id": "project-1"},
        "project_outcome_status": "pending",
    }
    payload.update({name: dict(section) for name in _SECTION_NAMES})
    return payload


def test_decision_cannot_be_replayed_for_changed_plan_payload() -> None:
    """Changing an authorized plan while retaining its ID must invalidate authority."""
    observed: list[dict[str, object]] = []
    authorized_plan = _plan()
    changed_plan = _plan(parameters={"scope": "materially-expanded"})

    with pytest.raises(PermissionError, match="immutable|content|hash"):
        _runner(observed).run(
            "probe",
            "project-1",
            "dataset:v1",
            plan=changed_plan,
            decision=_decision(authorized_plan),
            parameters={"scope": "materially-expanded"},
        )

    assert observed == []


def test_empty_planned_parameters_do_not_authorize_arbitrary_parameters() -> None:
    """An omitted parameter set means no parameters, not arbitrary parameters."""
    observed: list[dict[str, object]] = []
    plan = _plan()

    with pytest.raises(PermissionError, match="parameters"):
        _runner(observed).run(
            "probe",
            "project-1",
            "dataset:v1",
            plan=plan,
            decision=_decision(plan),
            parameters={"unreviewed": True},
        )

    assert observed == []


def test_tool_result_always_carries_the_authorized_plan_id() -> None:
    """Successful evidence must retain the plan provenance used to authorize it."""
    plan = _plan()
    result = _runner([]).run(
        "probe",
        "project-1",
        "dataset:v1",
        plan=plan,
        decision=_decision(plan),
    )

    assert result.experiment_plan_id == "plan-authorized"


def test_expired_lease_cannot_submit_without_waiting_for_another_lease_cycle(
    tmp_path: Path,
) -> None:
    """Lease expiry is an authority boundary even before another worker polls."""
    admin = open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'runtime.sqlite3'}", workspace=tmp_path
    )
    assignment = admin.start(
        project_id="lease-expiry-project",
        objective="Reject stale worker authority.",
        loop_policy=_loop_policy(),
        launch_worker=False,
    ).assignment
    runtime = TaskRuntimeService(admin.memory)
    leased = runtime.lease_ready_task(
        assignment.assignment_id,
        lease_owner="stale-worker",
        lease_seconds=1,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    assert leased is not None

    with pytest.raises(TaskRuntimeError, match="expired|active task lease"):
        runtime.submit_result(
            _completed_planning_result(leased.task.task_id, leased.attempt_id),
            lease_owner="stale-worker",
        )


def test_unexpired_inflight_result_survives_service_restart(tmp_path: Path) -> None:
    """A process restart must not discard a durable, still-valid task lease."""
    database_url = f"sqlite:///{tmp_path / 'runtime.sqlite3'}"
    admin = open_admin_service(database_url=database_url, workspace=tmp_path)
    assignment = admin.start(
        project_id="restart-project",
        objective="Resume a durable in-flight handoff.",
        loop_policy=_loop_policy(),
        launch_worker=False,
    ).assignment
    leased = TaskRuntimeService(admin.memory).lease_ready_task(
        assignment.assignment_id, lease_owner="worker-1"
    )
    assert leased is not None

    reopened = open_admin_service(database_url=database_url, workspace=tmp_path)
    status = TaskRuntimeService(reopened.memory).submit_result(
        _completed_planning_result(leased.task.task_id, leased.attempt_id),
        lease_owner="worker-1",
    )

    assert status == "succeeded"
    assert reopened.status(assignment.assignment_id).assignment.status == "completed"


def test_duplicate_result_is_rejected_after_service_restart(tmp_path: Path) -> None:
    """Re-delivery after a lost acknowledgement must not apply a result twice."""
    database_url = f"sqlite:///{tmp_path / 'runtime.sqlite3'}"
    admin = open_admin_service(database_url=database_url, workspace=tmp_path)
    assignment = admin.start(
        project_id="duplicate-project",
        objective="Apply a durable result exactly once.",
        loop_policy=_loop_policy(),
        launch_worker=False,
    ).assignment
    runtime = TaskRuntimeService(admin.memory)
    leased = runtime.lease_ready_task(assignment.assignment_id, lease_owner="worker-1")
    assert leased is not None
    result = _completed_planning_result(leased.task.task_id, leased.attempt_id)
    assert runtime.submit_result(result, lease_owner="worker-1") == "succeeded"

    reopened = open_admin_service(database_url=database_url, workspace=tmp_path)
    with pytest.raises(TaskRuntimeError, match="active task lease"):
        TaskRuntimeService(reopened.memory).submit_result(result, lease_owner="worker-1")


def test_report_contract_rejects_unknown_section_status() -> None:
    """A typo must not make an unrecognized evidence state look legitimate."""
    with pytest.raises(ValidationError, match="section_status"):
        StaticReportData.model_validate(_report_payload({"section_status": "compleet"}))


def test_incomplete_report_section_requires_a_reason() -> None:
    """Missing evidence must say why it is missing."""
    with pytest.raises(ValidationError, match="missing_or_blocked_reason"):
        StaticReportData.model_validate(_report_payload({"section_status": "failed"}))
