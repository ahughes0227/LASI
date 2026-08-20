"""Durable record of planning decisions, and the realized outcome of each.

`DomainStatePlanner` keeps one admissible plan and discards the rest, so a plan on its
own does not show that a decision was made.  Recording the choice together with the
alternatives it beat is what makes selection auditable, and what makes it learnable:
a dataset of chosen plans alone carries the preferences of the ranker that chose them.

Lives in the planner package rather than in `services.memory` because the dependency
runs planner -> memory, as it already does for the planner catalog.
"""

from __future__ import annotations

from services.contracts.models import StrictModel
from services.memory import OperationalMemory
from services.memory.models import (
    PlanningEpisode,
    ResearchAssignmentRecord,
    TaskAttemptRecord,
)

from .domain_models import DomainPlan
from .fingerprint import ProblemFingerprint


class PlanOutcome(StrictModel):
    """What actually happened to a recorded plan.

    `attributable` is false whenever the plan has no assignment: a plan that was produced
    but never dispatched has no outcome, which is different from having a bad one, and
    the two must not be averaged together by anything that learns from these records.
    """

    plan_id: str
    assignment_id: str | None
    attributable: bool
    assignment_status: str | None = None
    attempts: int = 0
    succeeded: int = 0
    failed: int = 0

    @property
    def resolved(self) -> bool:
        """Whether the assignment reached a terminal state."""
        return self.assignment_status in {"completed", "failed", "cancelled", "budget_exhausted"}


class PlanningEpisodeRecorder:
    """Writes planning decisions to operational memory and reads back their outcomes."""

    def __init__(self, memory: OperationalMemory) -> None:
        self.memory = memory

    def record(
        self,
        plan: DomainPlan,
        *,
        admissible_count: int | None = None,
        assignment_id: str | None = None,
        workflow_id: str | None = None,
        problem: ProblemFingerprint | None = None,
    ) -> PlanningEpisode:
        """Persist one planning decision.

        `admissible_count` defaults to what the retained alternatives imply, which is a
        lower bound: retention is capped, so a caller that knows the true size of the
        admissible set should pass it rather than let it be inferred.

        `problem` is what makes the episode findable later.  Omitting it records the
        decision but not the problem it addressed, so the episode can be audited and
        cannot be retrieved.
        """
        implied = len(plan.considered_alternatives) + (1 if plan.steps else 0)
        record = PlanningEpisode(
            plan_id=plan.plan_id,
            project_id=plan.goal.project_id,
            goal_id=plan.goal.goal_id,
            goal_description=plan.goal.description,
            observed_revision=plan.observed_revision,
            status=plan.status,
            ranker_id=plan.ranker_id,
            ranker_version=plan.ranker_version,
            chosen_capability_ids=[step.capability_id for step in plan.steps],
            considered_alternatives=[
                alternative.model_dump(mode="json") for alternative in plan.considered_alternatives
            ],
            admissible_count=admissible_count if admissible_count is not None else implied,
            problem_digest=problem.digest if problem else None,
            problem_fingerprint=problem.model_dump(mode="json") if problem else None,
            assignment_id=assignment_id,
            workflow_id=workflow_id,
        )
        return self.memory.add(record)

    def attach_execution(
        self, plan_id: str, *, assignment_id: str, workflow_id: str | None = None
    ) -> PlanningEpisode:
        """Link a recorded plan to the assignment that executes it.

        Separate from `record` because a plan is produced before it is dispatched, and
        an outcome can only be attributed once that link exists.
        """
        with self.memory.transaction() as session:
            record = session.get(PlanningEpisode, plan_id)
            if record is None:
                raise KeyError(f"no planning episode recorded for plan {plan_id!r}")
            record.assignment_id = assignment_id
            if workflow_id is not None:
                record.workflow_id = workflow_id
            session.flush()
            session.expunge(record)
        return record

    def outcome(self, plan_id: str) -> PlanOutcome:
        """Attribute a realized outcome to the decision that proposed it."""
        with self.memory.read_session() as session:
            record = session.get(PlanningEpisode, plan_id)
            if record is None:
                raise KeyError(f"no planning episode recorded for plan {plan_id!r}")
            if record.assignment_id is None:
                return PlanOutcome(plan_id=plan_id, assignment_id=None, attributable=False)
            assignment = session.get(ResearchAssignmentRecord, record.assignment_id)
            attempts = (
                session.query(TaskAttemptRecord)
                .filter(TaskAttemptRecord.assignment_id == record.assignment_id)
                .all()
            )
            return PlanOutcome(
                plan_id=plan_id,
                assignment_id=record.assignment_id,
                attributable=True,
                assignment_status=assignment.status if assignment else None,
                attempts=len(attempts),
                succeeded=sum(attempt.status == "succeeded" for attempt in attempts),
                failed=sum(attempt.status == "failed" for attempt in attempts),
            )

    def for_project(self, project_id: str) -> list[PlanningEpisode]:
        return self.memory.list_for_project(PlanningEpisode, project_id)
