"""What LASI records about its own decisions.

Two properties matter here. A planning decision must be reconstructable from the trace
alone -- which ranker chose, from how many options -- and token metering must never
contain a number nobody measured.
"""

from datetime import UTC, datetime

import pytest
from services.contracts import ActionTokenUsage, ProviderTokenUsage, TokenUsageStatus
from services.observability import MlflowTracer, PlanningTrace, trace_from_plan
from services.planner import ConsideredPlan, DomainGoal, DomainPlan, PlannedCapabilityStep

NOW = datetime.now(UTC)


@pytest.fixture
def tracer(tmp_path) -> MlflowTracer:
    return MlflowTracer(f"sqlite:///{tmp_path / 'mlflow.db'}", experiment="test")


def _read(tracer: MlflowTracer, run_id: str):
    from mlflow.tracking import MlflowClient

    return MlflowClient(tracking_uri=tracer.tracking_uri).get_run(run_id).data


def _trace(**overrides) -> PlanningTrace:
    base = {
        "plan_id": "plan-1",
        "project_id": "project-1",
        "goal_id": "goal-1",
        "status": "planned",
        "ranker_id": "episode-informed",
        "ranker_version": "1.0",
        "admissible_count": 3,
        "chosen_capability_ids": ["beta"],
    }
    return PlanningTrace(**{**base, **overrides})


def _usage(status: TokenUsageStatus, **overrides) -> ActionTokenUsage:
    base = {
        "action_usage_id": "usage-1",
        "project_id": "project-1",
        "action_id": "action-1",
        "action_type": "scientist_review",
        "status": status,
    }
    return ActionTokenUsage(**{**base, **overrides})


def test_a_decision_records_which_ranker_made_it(tracer: MlflowTracer) -> None:
    run_id = tracer.log_planning_decision(_trace())

    data = _read(tracer, run_id)

    assert data.params["ranker_id"] == "episode-informed"
    assert data.params["ranker_version"] == "1.0"


def test_a_decision_records_what_it_chose_from(tracer: MlflowTracer) -> None:
    """A forced move and a preference are indistinguishable without this."""
    run_id = tracer.log_planning_decision(_trace(admissible_count=4))

    data = _read(tracer, run_id)

    assert data.metrics["admissible_count"] == 4.0
    assert data.metrics["was_a_real_choice"] == 1.0


def test_a_forced_move_is_marked_as_one(tracer: MlflowTracer) -> None:
    run_id = tracer.log_planning_decision(_trace(admissible_count=1))

    assert _read(tracer, run_id).metrics["was_a_real_choice"] == 0.0


def test_the_basis_for_a_selection_is_recorded(tracer: MlflowTracer) -> None:
    run_id = tracer.log_planning_decision(
        _trace(precedent={"candidate-0": -0.5, "candidate-1": 1.0})
    )

    metrics = _read(tracer, run_id).metrics

    assert metrics["precedent.candidate-1"] == 1.0
    assert metrics["precedent.candidate-0"] == -0.5


def test_reported_usage_logs_the_receipt(tracer: MlflowTracer) -> None:
    usage = _usage(
        TokenUsageStatus.REPORTED,
        model_name="mock-1",
        usage=ProviderTokenUsage(
            reporting_source="provider-receipt",
            total_tokens=1200,
            input_tokens=1000,
            output_tokens=200,
            billed_cost_usd=0.42,
            reported_at=NOW,
        ),
    )
    with tracer.run("action") as active:
        tracer.log_token_usage(usage)
        run_id = active.info.run_id

    data = _read(tracer, run_id)

    assert data.metrics["total_tokens"] == 1200.0
    assert data.metrics["billed_cost_usd"] == 0.42
    assert data.tags["token_status"] == "reported"


def test_a_missing_receipt_logs_no_token_numbers(tracer: MlflowTracer) -> None:
    """The rule that outlives this adapter: never invent a number nobody measured."""
    usage = _usage(
        TokenUsageStatus.NOT_AVAILABLE,
        unavailable_reason="provider returned no usage block",
    )
    with tracer.run("action") as active:
        tracer.log_token_usage(usage)
        run_id = active.info.run_id

    data = _read(tracer, run_id)

    assert data.tags["token_status"] == "not_available"
    assert data.tags["token_unavailable_reason"] == "provider returned no usage block"
    # An estimate logged beside real receipts would be indistinguishable from one.
    assert "total_tokens" not in data.metrics
    assert "billed_cost_usd" not in data.metrics


def test_a_non_token_action_records_that_it_has_no_tokens(tracer: MlflowTracer) -> None:
    with tracer.run("action") as active:
        tracer.log_token_usage(_usage(TokenUsageStatus.NOT_APPLICABLE))
        run_id = active.info.run_id

    data = _read(tracer, run_id)

    assert data.tags["token_status"] == "not_applicable"
    assert "total_tokens" not in data.metrics


def test_estimated_usage_cannot_be_constructed_at_all() -> None:
    """The contract refuses it before any adapter gets the chance to log it."""
    with pytest.raises(ValueError):
        ProviderTokenUsage(reporting_source="token estimate from prompt", total_tokens=100)


def test_metering_outside_a_run_is_refused(tracer: MlflowTracer) -> None:
    """Otherwise MLflow invents an orphan run that belongs to no action."""
    with pytest.raises(RuntimeError):
        tracer.log_token_usage(_usage(TokenUsageStatus.NOT_APPLICABLE))


def test_a_trace_can_be_built_from_a_real_plan(tracer: MlflowTracer) -> None:
    plan = DomainPlan(
        plan_id="domain-plan-1",
        goal=DomainGoal(
            goal_id="goal-1",
            project_id="project-1",
            description="reach ready",
            desired_state=[
                {"subject": "project", "predicate": "ready", "operator": "equals", "value": True}
            ],
        ),
        observed_revision=2,
        status="planned",
        steps=[PlannedCapabilityStep(step_id="s1", capability_id="beta", side_effect_class="read")],
        considered_alternatives=[
            ConsideredPlan(
                rank=2,
                capability_ids=["alpha"],
                step_count=1,
                side_effect_score=1,
                approval_count=0,
            )
        ],
        ranker_id="episode-informed",
        ranker_version="1.0",
    )

    trace = trace_from_plan(plan, problem_digest="abc123", scaffold_revision="1.0")
    run_id = tracer.log_planning_decision(trace)

    data = _read(tracer, run_id)

    assert trace.admissible_count == 2
    assert data.params["chosen_capability_ids"] == "beta"
    assert data.params["problem_digest"] == "abc123"
    assert data.params["scaffold_revision"] == "1.0"
