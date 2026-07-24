"""Focused tests for outcome state and event invariants."""

from datetime import UTC, datetime

import pytest

from lasi.memory import (
    Approval,
    Base,
    Decision,
    OperationalMemory,
    Project,
    create_engine,
    create_session_factory,
)
from lasi.outcomes import (
    InvalidOutcomeTransition,
    MissingProductionEvidence,
    OutcomeService,
)


@pytest.fixture
def outcome_service() -> OutcomeService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    memory.add(Project(project_id="project-1", project_name="P", problem_type="x", modality="y"))
    memory.add(
        Decision(
            decision_id="decision-1",
            project_id="project-1",
            decision="allow",
            allowed=True,
            payload={"action_requested": "deployment"},
        )
    )
    memory.add(
        Approval(
            approval_id="approval-1",
            project_id="project-1",
            decision_id="decision-1",
            action_type="deployment",
            approval_status="approved",
        )
    )
    memory.add(Project(project_id="project-2", project_name="P2", problem_type="x", modality="y"))
    memory.add(
        Approval(
            approval_id="approval-2",
            project_id="project-2",
            decision_id="decision-1",
            action_type="deployment",
            approval_status="approved",
        )
    )
    memory.add(
        Decision(
            decision_id="decision-2",
            project_id="project-1",
            decision="allow",
            allowed=True,
            payload={"action_requested": "run_local_experiment"},
        )
    )
    memory.add(
        Approval(
            approval_id="approval-3",
            project_id="project-1",
            decision_id="decision-2",
            action_type="run_local_experiment",
            approval_status="approved",
        )
    )
    return OutcomeService(memory, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))


def test_current_is_empty_until_first_outcome(outcome_service: OutcomeService) -> None:
    assert outcome_service.current("project-1") is None


def test_production_success_requires_evidence(outcome_service: OutcomeService) -> None:
    outcome_service.transition(
        "project-1",
        "deployed",
        reason="released",
        owner="owner",
        decision_id="decision-1",
        approval_id="approval-1",
    )

    with pytest.raises(MissingProductionEvidence):
        outcome_service.transition(
            "project-1",
            "successful_in_production",
            reason="looks good",
            owner="owner",
            decision_id="decision-1",
            approval_id="approval-1",
        )


def test_deployed_to_failed_in_production_preserves_history(
    outcome_service: OutcomeService,
) -> None:
    outcome_service.transition(
        "project-1",
        "deployed",
        reason="released",
        owner="owner",
        decision_id="decision-1",
        approval_id="approval-1",
    )
    failed = outcome_service.transition(
        "project-1",
        "failed_in_production",
        reason="domain shift",
        owner="operator",
        evidence=["artifact://monitoring/1"],
        decision_id="decision-1",
        approval_id="approval-1",
    )

    current = outcome_service.current("project-1")
    assert current is not None
    assert current.current_status == "failed_in_production"
    assert failed.previous_status == "deployed"
    assert [event.new_status for event in outcome_service.events("project-1")] == [
        "deployed",
        "failed_in_production",
    ]


def test_invalid_transition_is_rejected(outcome_service: OutcomeService) -> None:
    with pytest.raises(InvalidOutcomeTransition):
        outcome_service.transition(
            "project-1",
            "successful_in_production",
            reason="not deployed",
            owner="owner",
            evidence=["e"],
            decision_id="decision-1",
            approval_id="approval-1",
        )


def test_deployment_requires_linked_authorization(outcome_service: OutcomeService) -> None:
    with pytest.raises(ValueError, match="decision_id and approval_id"):
        outcome_service.transition("project-1", "deployed", reason="released", owner="owner")


def test_deployment_rejects_approval_from_another_project(
    outcome_service: OutcomeService,
) -> None:
    with pytest.raises(ValueError, match="authorization"):
        outcome_service.transition(
            "project-1",
            "deployed",
            reason="released",
            owner="owner",
            decision_id="decision-1",
            approval_id="approval-2",
        )


def test_deployment_requires_decision_to_authorize_deployment(
    outcome_service: OutcomeService,
) -> None:
    with pytest.raises(ValueError, match="authorization"):
        outcome_service.transition(
            "project-1",
            "deployed",
            reason="released",
            owner="owner",
            decision_id="decision-2",
            approval_id="approval-3",
        )
