"""The research loop, plateau stopping, and escalation live in the SQL runtime.

These behaviours used to sit on a second control plane that no worker ever
launched, so none of them could fire during a real assignment.  They are
exercised here through the runtime that actually runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from services.admin import AssignmentAdminService, open_admin_service
from services.contracts import (
    AgentResult,
    CriterionResult,
    ResearchAlternative,
    ResearchAttempt,
    ResearchEscalation,
    ResearchLoopPolicy,
    ResearchLoopState,
    TaskGraphProposal,
    TaskSpec,
)
from services.memory import ResearchLoopStateRecord, RuntimeTaskRecord
from services.runtime import TaskRuntimeService


def _admin(tmp_path: Path) -> AssignmentAdminService:
    return open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )


def _assignment(admin: AssignmentAdminService, **policy: object) -> str:
    values: dict[str, object] = {
        "objective_metric": "score",
        "objective_direction": "maximize",
        "minimum_meaningful_improvement": 0.001,
        "plateau_patience": 3,
    }
    values.update(policy)
    return admin.start(
        project_id="loop-project",
        objective="find what limits the score",
        loop_policy=ResearchLoopPolicy(**values),
        launch_worker=False,
    ).assignment.assignment_id


def _revision(admin: AssignmentAdminService, assignment_id: str) -> int:
    return admin.status(assignment_id).assignment.graph_revision


def _satisfied(*criterion_ids: str) -> list[CriterionResult]:
    return [
        CriterionResult(
            criterion_id=criterion_id,
            status="satisfied",
            evidence_refs=[f"sql:evidence:{criterion_id}"],
        )
        for criterion_id in criterion_ids
    ]


def _attempt(iteration: int, *, score: float, signature: list[str]) -> ResearchAttempt:
    return ResearchAttempt(
        attempt_id=f"attempt-{iteration}",
        iteration=iteration,
        experiment_plan_id=f"plan-{iteration}",
        status="succeeded",
        score=score,
        hypothesis=f"hypothesis-{iteration}",
        research_basis=[f"evidence-{iteration}"],
        approach_signature=signature,
        novel_dimensions=["model_family"],
        novelty_score=1.0,
    )


def _analysis_task(admin: AssignmentAdminService, assignment_id: str, index: int) -> str:
    """Queue and lease one analysis task, returning its attempt id."""
    runtime = TaskRuntimeService(admin.memory)
    runtime.install_default_rubrics()
    ingestion = runtime.ingest_proposal(
        TaskGraphProposal(
            proposal_id=f"proposal-{index}",
            assignment_id=assignment_id,
            project_id="loop-project",
            observed_revision=_revision(admin, assignment_id),
            rationale="Interpret the latest attempt.",
            tasks=[
                TaskSpec(
                    task_id=f"task-analysis-{index}",
                    project_id="loop-project",
                    task_type="result_analysis",
                    agent_role="scientist-reviewer",
                    description="Interpret the attempt.",
                    rubric_id="scientist-reasoning",
                    rubric_version="1.0",
                    # Outranks the bootstrap orchestration task so the analysis
                    # work leases first and the assignment stays open.
                    priority=200,
                )
            ],
        )
    )
    assert ingestion.accepted, ingestion.rejection_reason
    leased = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert leased is not None and leased.task.task_id == f"task-analysis-{index}"
    return leased.attempt_id


def _loop_state(admin: AssignmentAdminService, assignment_id: str) -> ResearchLoopState:
    record = admin.memory.get(ResearchLoopStateRecord, assignment_id)
    assert record is not None
    return ResearchLoopState.model_validate(record.payload)


def test_submitting_an_attempt_advances_the_durable_research_loop(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    attempt_id = _analysis_task(admin, assignment_id, 1)

    runtime.submit_result(
        AgentResult(
            task_id="task-analysis-1",
            attempt_id=attempt_id,
            status="completed",
            summary="First baseline scored 0.70.",
            criterion_results=_satisfied(
                "observed_vs_expected", "alternative_hypotheses", "discriminating_test"
            ),
            research_attempt=_attempt(1, score=0.70, signature=["logistic", "raw-features"]),
        ),
        lease_owner="runtime-1",
    )

    state = _loop_state(admin, assignment_id)
    assert state.status == "running"
    assert state.best_score == 0.70
    assert state.best_attempt_id == "attempt-1"
    assert state.reason == "objective_improved"
    # An improvement must be interpreted before another implementation branch.
    assert state.next_phase == "review"


def test_near_duplicate_attempts_do_not_consume_plateau_patience(tmp_path: Path) -> None:
    """Novelty is measured against prior signatures, not the agent's own claim."""
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)

    for index, score in ((1, 0.70), (2, 0.70), (3, 0.70)):
        attempt_id = _analysis_task(admin, assignment_id, index)
        runtime.submit_result(
            AgentResult(
                task_id=f"task-analysis-{index}",
                attempt_id=attempt_id,
                status="completed",
                summary=f"Attempt {index} retuned the same family.",
                criterion_results=_satisfied(
                    "observed_vs_expected", "alternative_hypotheses", "discriminating_test"
                ),
                # Identical signature each time, and the agent insists it is novel.
                research_attempt=_attempt(index, score=score, signature=["logistic", "raw"]),
            ),
            lease_owner="runtime-1",
        )

    state = _loop_state(admin, assignment_id)
    assert state.status == "running"
    assert state.non_improving_novel_attempts == 0
    assert state.reason == "candidate_insufficiently_divergent"
    assert admin.status(assignment_id).assignment.status == "active"


def test_plateau_after_divergent_attempts_settles_the_assignment(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    signatures = [
        ["logistic", "raw"],
        ["gradient-boosting", "target-encoded"],
        ["neural", "embedding"],
        ["nearest-neighbour", "metric-learned"],
    ]

    for index, signature in enumerate(signatures, start=1):
        attempt_id = _analysis_task(admin, assignment_id, index)
        runtime.submit_result(
            AgentResult(
                task_id=f"task-analysis-{index}",
                attempt_id=attempt_id,
                status="completed",
                summary=f"Attempt {index} diverged and did not improve.",
                criterion_results=_satisfied(
                    "observed_vs_expected", "alternative_hypotheses", "discriminating_test"
                ),
                research_attempt=_attempt(index, score=0.70, signature=signature),
            ),
            lease_owner="runtime-1",
        )

    state = _loop_state(admin, assignment_id)
    assert state.status == "plateaued"
    assert state.reason == "plateau_after_divergent_attempts"

    assignment = admin.status(assignment_id).assignment
    assert assignment.status == "plateaued"
    assert "plateau_after_divergent_attempts" in (assignment.latest_summary or "")
    assert runtime.lease_ready_task(assignment_id, lease_owner="runtime-1") is None
    events = [event.event_type for event in admin.events(assignment_id)]
    assert "assignment_started" in events


def test_escalation_stops_the_assignment_and_records_its_question(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    runtime.install_default_rubrics()
    leased = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert leased is not None

    runtime.submit_result(
        AgentResult(
            task_id=leased.task.task_id,
            attempt_id=leased.attempt_id,
            status="completed",
            summary="The dataset boundary needs a human decision.",
            criterion_results=_satisfied(
                "separate_observation_inference", "smallest_discriminating_next_step"
            ),
            recommended_assignment_status="escalate",
            escalation=ResearchEscalation(
                escalation_id="esc-boundary",
                question="May the benchmark split be redefined?",
                necessity="essential",
                alternatives_considered=[
                    ResearchAlternative(
                        description="tune within the current split",
                        feasible=False,
                        authorized=True,
                        rejection_reason="already exhausted across three families",
                    )
                ],
            ),
        ),
        lease_owner="runtime-1",
    )

    assignment = admin.status(assignment_id).assignment
    assert assignment.status == "escalated"
    assert assignment.pending_escalation_id == "esc-boundary"
    assert assignment.pending_escalation_question == "May the benchmark split be redefined?"
    assert runtime.lease_ready_task(assignment_id, lease_owner="runtime-1") is None


def test_escalation_requires_the_payload_and_status_together() -> None:
    with pytest.raises(ValueError, match="accompany each other"):
        AgentResult(
            task_id="task-1",
            attempt_id="attempt-1",
            status="completed",
            summary="Escalating without saying why.",
            criterion_results=[],
            recommended_assignment_status="escalate",
        )


def test_a_settled_assignment_accepts_no_further_proposals(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    runtime.install_default_rubrics()
    leased = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert leased is not None
    runtime.submit_result(
        AgentResult(
            task_id=leased.task.task_id,
            attempt_id=leased.attempt_id,
            status="completed",
            summary="Objective met.",
            criterion_results=_satisfied(
                "separate_observation_inference", "smallest_discriminating_next_step"
            ),
            recommended_assignment_status="complete",
        ),
        lease_owner="runtime-1",
    )

    ingestion = runtime.ingest_proposal(
        TaskGraphProposal(
            proposal_id="proposal-after-completion",
            assignment_id=assignment_id,
            project_id="loop-project",
            observed_revision=_revision(admin, assignment_id),
            rationale="Queue more work on a finished assignment.",
            tasks=[
                TaskSpec(
                    task_id="task-too-late",
                    project_id="loop-project",
                    task_type="result_analysis",
                    agent_role="scientist-reviewer",
                    description="Should never be leased.",
                    rubric_id="scientist-reasoning",
                    rubric_version="1.0",
                )
            ],
        )
    )

    assert not ingestion.accepted
    assert "accepts no further tasks" in (ingestion.rejection_reason or "")
    assert admin.memory.get(RuntimeTaskRecord, "task-too-late") is None
