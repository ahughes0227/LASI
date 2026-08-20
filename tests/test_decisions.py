"""Focused tests for deterministic decision and governance behavior."""

from datetime import UTC, datetime

from services.contracts import ApprovalRecord, ExperimentPlan, ToolSpec
from services.contracts.models import BudgetEstimate
from services.decisions import DecisionContext, DecisionGate, Recommendation
from services.experiments import experiment_plan_content_hash


def _recommendation(action: str) -> Recommendation:
    return Recommendation("recommendation-1", "project-1", action)


def _plan(*, backend: str = "local", budget: BudgetEstimate | None = None) -> ExperimentPlan:
    return ExperimentPlan(
        experiment_plan_id="plan-1",
        project_id="project-1",
        dataset_version="dataset-v1",
        hypothesis="h",
        reason_for_experiment="diagnosis",
        experiment_type="baseline_probe",
        planned_tool_runs=[{"tool_id": "baseline", "run_id": "run-1"}],
        execution_backend=backend,
        expected_signal="signal",
        success_criteria="pass",
        failure_criteria="fail",
        budget_estimate=budget or BudgetEstimate(),
    )


def _context(**kwargs: object) -> DecisionContext:
    values: dict[str, object] = {
        "dataset_status": "approved",
        "available_tools": (
            ToolSpec(
                tool_id="baseline",
                name="Baseline",
                version="1",
                supported_modalities=["tabular"],
                supported_problem_types=["classification"],
                supported_execution_backends=["local"],
            ),
        ),
        "available_budget": BudgetEstimate(cost_usd=10, cpu_hours=10),
    }
    values.update(kwargs)
    return DecisionContext(**values)


def test_recommendation_cannot_execute_without_a_compiled_plan() -> None:
    decision = DecisionGate().evaluate(_recommendation("run_local_experiment"), context=_context())

    assert decision.decision == "request_clarification"
    assert not decision.allowed
    assert "experiment_plan" in decision.missing_inputs


def test_all_experiment_gates_allow_a_valid_local_plan() -> None:
    plan = _plan()
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"), context=_context(), plan=plan
    )

    assert decision.decision == "allow"
    assert decision.allowed
    assert decision.experiment_plan_hash == experiment_plan_content_hash(plan)
    assert decision.policy_checks == {
        "privacy": True,
        "budget": True,
        "dataset_status": True,
        "comparability": True,
        "tool_availability": True,
        "project_scope": True,
    }


def test_plan_approval_requirement_is_enforced_by_the_gate() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"),
        context=_context(),
        plan=_plan_with_approval_required(),
    )

    assert decision.decision == "escalate_for_approval"
    assert not decision.allowed
    assert decision.approval_required
    assert decision.blocked_by == ["approval_required"]


def test_plan_for_another_project_is_blocked() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"),
        context=_context(),
        plan=_plan_with(project_id="project-2"),
    )

    assert not decision.allowed
    assert decision.blocked_by == ["project_scope"]


def _plan_with_approval_required() -> ExperimentPlan:
    return _plan_with(approval_required=True)


def _plan_with(**kwargs: object) -> ExperimentPlan:
    values = _plan().model_dump()
    values.update(kwargs)
    return ExperimentPlan.model_validate(values)


def test_budget_tool_dataset_and_comparability_failures_block() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"),
        context=_context(
            dataset_status="draft",
            dataset_comparable=False,
            available_budget=BudgetEstimate(cpu_hours=1),
        ),
        plan=_plan(budget=BudgetEstimate(cpu_hours=2)),
    )

    assert decision.decision == "block"
    assert set(decision.blocked_by) == {"budget", "dataset_status", "comparability"}


def test_unavailable_tool_blocks() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"), context=_context(available_tools=()), plan=_plan()
    )

    assert decision.decision == "block"
    assert decision.blocked_by == ["tool_availability"]


def test_duplicate_work_requires_an_explicit_replication_reason() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_local_experiment"),
        context=_context(duplicate_found=True),
        plan=_plan(),
    )

    assert decision.decision == "block"
    assert decision.blocked_by == ["duplicate_work"]


def test_remote_experiment_requires_trusted_available_host() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("run_remote_experiment"), context=_context(), plan=_plan(backend="remote")
    )

    assert decision.decision == "block"
    assert "remote_trust" in decision.blocked_by


def test_privacy_gate_blocks_thumbnails_in_summary_mode() -> None:
    decision = DecisionGate().evaluate(
        _recommendation("send_thumbnails"),
        context=_context(
            privacy_mode="summary_only_to_scientist",
            provider_privacy_capabilities=("thumbnails_allowed",),
        ),
    )

    assert decision.decision == "block"
    assert decision.blocked_by == ["privacy"]


def test_protected_dataset_change_becomes_proposal_without_approval() -> None:
    decision = DecisionGate().evaluate(_recommendation("modify_labels"), context=_context())

    assert decision.decision == "convert_to_proposal"
    assert not decision.allowed
    assert decision.approval_required
    assert decision.next_action == "submit_proposal"


def test_protected_action_needs_matching_current_approval() -> None:
    approval = ApprovalRecord(
        approval_id="approval-1",
        project_id="project-1",
        action_type="modify_labels",
        risk_level="high",
        requested_by="operator",
        approved_by="reviewer",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )
    decision = DecisionGate().evaluate(
        _recommendation("modify_labels"), context=_context(existing_approval=approval)
    )

    assert decision.decision == "allow"
    assert decision.allowed


def test_protected_action_rejects_approval_for_another_project() -> None:
    approval = ApprovalRecord(
        approval_id="approval-1",
        project_id="project-2",
        action_type="modify_labels",
        risk_level="high",
        requested_by="operator",
        approved_by="reviewer",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )
    decision = DecisionGate().evaluate(
        _recommendation("modify_labels"), context=_context(existing_approval=approval)
    )

    assert not decision.allowed
    assert decision.blocked_by == ["approval_required"]


def test_unknown_action_is_never_authorized() -> None:
    decision = DecisionGate().evaluate(_recommendation("run_anything"), context=_context())

    assert decision.decision == "request_clarification"
    assert not decision.allowed
