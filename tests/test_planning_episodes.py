"""Planning decisions are recorded with their rejected alternatives, and can be judged.

A plan on its own shows only what LASI did.  These tests pin the two properties that
make the record useful later: the alternatives survive, and a realized outcome is
attributed to the decision that proposed it — or explicitly not attributed at all.
"""

from datetime import UTC, datetime, timedelta

import pytest
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import (
    PlanningEpisode,
    Project,
    ReasoningRubricRecord,
    ResearchAssignmentRecord,
    RuntimeTaskRecord,
    TaskAttemptRecord,
    TaskGraphProposalRecord,
)
from services.planner import ConsideredPlan, DomainGoal, DomainPlan, PlannedCapabilityStep
from services.planner.episodes import PlanningEpisodeRecorder

NOW = datetime.now(UTC)


@pytest.fixture
def memory() -> OperationalMemory:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = OperationalMemory(create_session_factory(engine))
    store.add(
        Project(
            project_id="project-1",
            project_name="P",
            problem_type="classification",
            modality="tabular",
        )
    )
    return store


@pytest.fixture
def recorder(memory: OperationalMemory) -> PlanningEpisodeRecorder:
    return PlanningEpisodeRecorder(memory)


def _plan(*, status: str = "planned", alternatives: int = 2) -> DomainPlan:
    return DomainPlan(
        plan_id="domain-plan-1",
        goal=DomainGoal(
            goal_id="goal-1",
            project_id="project-1",
            description="reach ready",
            desired_state=[
                {"subject": "project", "predicate": "ready", "operator": "equals", "value": True}
            ],
        ),
        observed_revision=4,
        status=status,
        steps=[
            PlannedCapabilityStep(step_id="step-1", capability_id="alpha", side_effect_class="read")
        ],
        considered_alternatives=[
            ConsideredPlan(
                rank=rank,
                capability_ids=[f"cap-{rank}"],
                step_count=1,
                side_effect_score=rank,
                approval_count=0,
            )
            for rank in range(2, 2 + alternatives)
        ],
    )


def _assignment(memory: OperationalMemory, assignment_id: str, status: str) -> None:
    memory.add(
        ResearchAssignmentRecord(
            assignment_id=assignment_id,
            project_id="project-1",
            objective="o",
            status=status,
        )
    )


def _attempt(memory: OperationalMemory, assignment_id: str, task_id: str, status: str) -> None:
    """Create the task graph a real attempt hangs from, then the attempt itself."""
    if memory.get(TaskGraphProposalRecord, "proposal-1") is None:
        memory.add(
            ReasoningRubricRecord(
                rubric_key="none", rubric_id="none", version="1.0", capability="research"
            )
        )
        memory.add(
            TaskGraphProposalRecord(
                proposal_id="proposal-1",
                assignment_id=assignment_id,
                project_id="project-1",
                observed_revision=1,
                status="accepted",
            )
        )
    memory.add(
        RuntimeTaskRecord(
            task_id=task_id,
            assignment_id=assignment_id,
            project_id="project-1",
            proposal_id="proposal-1",
            task_type="orchestration",
            agent_role="coordinator",
            status="completed",
            sequence=1,
            rubric_key="none",
        )
    )
    memory.add(
        TaskAttemptRecord(
            attempt_id=f"attempt-{task_id}-{status}",
            task_id=task_id,
            assignment_id=assignment_id,
            project_id="project-1",
            status=status,
            agent_role="coordinator",
            lease_owner="runtime-1",
            lease_expires_at=NOW + timedelta(minutes=15),
            context_snapshot_id="ctx-1",
            started_at=NOW,
        )
    )


def test_rejected_alternatives_survive_the_write(recorder: PlanningEpisodeRecorder) -> None:
    record = recorder.record(_plan())

    assert record.chosen_capability_ids == ["alpha"]
    assert [item["rank"] for item in record.considered_alternatives] == [2, 3]
    assert record.ranker_id == "lexicographic"


def test_admissible_count_defaults_to_a_lower_bound(recorder: PlanningEpisodeRecorder) -> None:
    # Retention is capped, so the inferred count is the chosen plan plus what was kept.
    assert recorder.record(_plan(alternatives=2)).admissible_count == 3


def test_admissible_count_can_be_supplied_when_retention_truncated(
    recorder: PlanningEpisodeRecorder,
) -> None:
    record = recorder.record(_plan(alternatives=2), admissible_count=57)

    assert record.admissible_count == 57


def test_an_undispatched_plan_has_no_attributable_outcome(
    recorder: PlanningEpisodeRecorder,
) -> None:
    recorder.record(_plan())
    outcome = recorder.outcome("domain-plan-1")

    # Distinct from a bad outcome: nothing was run, so nothing can be judged.
    assert outcome.attributable is False
    assert outcome.assignment_id is None
    assert outcome.resolved is False


def test_outcome_is_attributed_through_the_assignment(
    memory: OperationalMemory, recorder: PlanningEpisodeRecorder
) -> None:
    _assignment(memory, "assignment-1", "completed")
    recorder.record(_plan())
    recorder.attach_execution("domain-plan-1", assignment_id="assignment-1", workflow_id="wf-1")
    _attempt(memory, "assignment-1", "task-1", "succeeded")
    _attempt(memory, "assignment-1", "task-2", "failed")

    outcome = recorder.outcome("domain-plan-1")

    assert outcome.attributable is True
    assert outcome.assignment_status == "completed"
    assert (outcome.attempts, outcome.succeeded, outcome.failed) == (2, 1, 1)
    assert outcome.resolved is True


def test_a_running_assignment_is_attributable_but_unresolved(
    memory: OperationalMemory, recorder: PlanningEpisodeRecorder
) -> None:
    _assignment(memory, "assignment-2", "running")
    recorder.record(_plan())
    recorder.attach_execution("domain-plan-1", assignment_id="assignment-2")

    outcome = recorder.outcome("domain-plan-1")

    assert outcome.attributable is True
    assert outcome.resolved is False


def test_attaching_an_unknown_plan_is_refused(recorder: PlanningEpisodeRecorder) -> None:
    with pytest.raises(KeyError):
        recorder.attach_execution("missing", assignment_id="assignment-1")


def test_episodes_are_listed_per_project(
    memory: OperationalMemory, recorder: PlanningEpisodeRecorder
) -> None:
    recorder.record(_plan())

    assert [item.plan_id for item in recorder.for_project("project-1")] == ["domain-plan-1"]
    assert recorder.for_project("other") == []


def test_project_foreign_key_is_enforced(memory: OperationalMemory) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        memory.add(
            PlanningEpisode(
                plan_id="orphan",
                project_id="no-such-project",
                goal_id="g",
                goal_description="d",
                observed_revision=1,
                status="planned",
                ranker_id="lexicographic",
                ranker_version="1.0",
                chosen_capability_ids=[],
                considered_alternatives=[],
                admissible_count=0,
            )
        )
