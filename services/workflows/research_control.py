"""Semantic control plane for durable research agendas and coordinator directives."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.contracts import (
    CoordinatorDirective,
    ResearchAction,
    ResearchAgenda,
    ResearchLoopState,
)
from services.memory import (
    Decision,
    ExperimentPlan,
    ResearchActionRecord,
    ResearchAgendaRecord,
    ResearchAssignmentRecord,
    ResearchLoopStateRecord,
)

from .research_loop import ResearchLoopController

_REVIEW_ACTIONS = frozenset({"error_analysis", "evidence_review", "scientist_review"})


class ResearchControlError(ValueError):
    """A proposed coordinator transition violates the authoritative agenda."""


class ResearchControlService:
    """Validate and persist one agenda transition inside the caller's transaction."""

    def validate(
        self, session: Session, assignment_id: str, directive: CoordinatorDirective
    ) -> None:
        agenda = session.scalar(
            select(ResearchAgendaRecord).where(ResearchAgendaRecord.assignment_id == assignment_id)
        )
        if agenda is None:
            raise ResearchControlError("assignment has no authoritative research agenda")
        if directive.current_action_id != agenda.current_action_id:
            raise ResearchControlError(
                "directive does not advance the agenda's required current action"
            )
        action_record = session.get(ResearchActionRecord, agenda.current_action_id)
        if action_record is None:
            raise ResearchControlError("agenda current action is missing")
        action = ResearchAction.model_validate(action_record.payload)
        if action.status not in {"pending", "active"}:
            raise ResearchControlError("agenda current action is not actionable")
        self._require_plan_authorization(session, action, directive)

        completed = action.action_id in directive.completed_action_ids
        if directive.action == "complete" and not completed:
            raise ResearchControlError("assignment completion must complete the current action")
        if directive.action == "continue" and completed and directive.next_action is None:
            raise ResearchControlError("completed action requires a durable next action")
        if directive.next_action is not None:
            self._validate_next_action(session, agenda, action, directive.next_action)
        if directive.action == "escalate":
            if not directive.alternatives_considered:
                raise ResearchControlError("escalation requires evaluated alternatives")
            if any(item.feasible and item.authorized for item in directive.alternatives_considered):
                raise ResearchControlError(
                    "escalation rejected because a feasible authorized alternative remains"
                )

        if directive.research_attempt is not None:
            loop_record = session.get(ResearchLoopStateRecord, assignment_id)
            if loop_record is None:
                raise ResearchControlError("research loop state is missing")
            state = ResearchLoopState.model_validate(loop_record.payload)
            advanced = ResearchLoopController().record_attempt(state, directive.research_attempt)
            if advanced.next_phase == "review":
                if (
                    directive.next_action is None
                    or directive.next_action.action_type not in _REVIEW_ACTIONS
                ):
                    raise ResearchControlError(
                        "meaningful improvement requires error analysis or scientist review next"
                    )

    def apply(
        self, session: Session, assignment_id: str, directive: CoordinatorDirective
    ) -> ResearchAction:
        agenda_record = session.scalar(
            select(ResearchAgendaRecord).where(ResearchAgendaRecord.assignment_id == assignment_id)
        )
        assert agenda_record is not None
        current_record = session.get(ResearchActionRecord, agenda_record.current_action_id)
        assert current_record is not None
        current = ResearchAction.model_validate(current_record.payload)

        if directive.research_attempt is not None:
            loop_record = session.get(ResearchLoopStateRecord, assignment_id)
            assert loop_record is not None
            state = ResearchLoopState.model_validate(loop_record.payload)
            advanced = ResearchLoopController().record_attempt(state, directive.research_attempt)
            loop_record.status = advanced.status
            loop_record.next_phase = advanced.next_phase
            loop_record.payload = advanced.model_dump(mode="json")

        if current.action_id in directive.completed_action_ids:
            current = current.model_copy(
                update={"status": "completed", "evidence_refs": directive.evidence_refs}
            )
            current_record.status = "completed"
            current_record.payload = current.model_dump(mode="json")

        if directive.next_action is not None:
            next_action = directive.next_action
            session.add(
                ResearchActionRecord(
                    action_id=next_action.action_id,
                    agenda_id=agenda_record.agenda_id,
                    project_id=next_action.project_id,
                    action_type=next_action.action_type,
                    status=next_action.status,
                    sequence=next_action.sequence,
                    experiment_plan_id=next_action.experiment_plan_id,
                    payload=next_action.model_dump(mode="json"),
                )
            )
            agenda_record.current_action_id = next_action.action_id
            agenda_record.revision += 1
            agenda = ResearchAgenda.model_validate(agenda_record.payload).model_copy(
                update={
                    "current_action_id": next_action.action_id,
                    "active_experiment_plan_id": next_action.experiment_plan_id,
                    "revision": agenda_record.revision,
                }
            )
            agenda_record.payload = agenda.model_dump(mode="json")
            return next_action
        return current

    @staticmethod
    def _require_plan_authorization(
        session: Session, action: ResearchAction, directive: CoordinatorDirective
    ) -> None:
        if not action.requires_experiment_plan:
            return
        if directive.experiment_plan_id != action.experiment_plan_id:
            raise ResearchControlError("directive does not reference the action's experiment plan")
        plan = session.get(ExperimentPlan, action.experiment_plan_id)
        if plan is None or plan.project_id != action.project_id:
            raise ResearchControlError("required experiment plan is not in operational memory")
        decision = session.scalar(
            select(Decision).where(
                Decision.experiment_plan_id == action.experiment_plan_id,
                Decision.allowed.is_(True),
            )
        )
        if decision is None:
            raise ResearchControlError("required experiment plan has no allowing decision")
        if directive.decision_id is not None and directive.decision_id != decision.decision_id:
            raise ResearchControlError("directive references a different decision")

    @classmethod
    def _validate_next_action(
        cls,
        session: Session,
        agenda: ResearchAgendaRecord,
        current: ResearchAction,
        next_action: ResearchAction,
    ) -> None:
        if next_action.project_id != agenda.project_id:
            raise ResearchControlError("next action belongs to another project")
        if next_action.sequence != current.sequence + 1:
            raise ResearchControlError("next action sequence must be contiguous")
        if session.get(ResearchActionRecord, next_action.action_id) is not None:
            raise ResearchControlError("next action id already exists")
        if next_action.requires_experiment_plan:
            plan = session.get(ExperimentPlan, next_action.experiment_plan_id)
            if plan is None:
                raise ResearchControlError("next action references an unpersisted experiment plan")
            decision = session.scalar(
                select(Decision).where(
                    Decision.experiment_plan_id == next_action.experiment_plan_id,
                    Decision.allowed.is_(True),
                )
            )
            if decision is None:
                raise ResearchControlError(
                    "next action references a plan without an allowing decision"
                )

    def audit(self, session: Session, assignment_id: str) -> list[str]:
        issues: list[str] = []
        agenda = session.scalar(
            select(ResearchAgendaRecord).where(ResearchAgendaRecord.assignment_id == assignment_id)
        )
        if agenda is None:
            return ["missing_research_agenda"]
        assignment = session.get(ResearchAssignmentRecord, assignment_id)
        if assignment is None:
            issues.append("missing_assignment")
        elif assignment.payload.get("current_action_id") != agenda.current_action_id:
            issues.append("assignment_agenda_projection_mismatch")
        if agenda.payload.get("current_action_id") != agenda.current_action_id:
            issues.append("agenda_payload_projection_mismatch")
        action = session.get(ResearchActionRecord, agenda.current_action_id)
        if action is None:
            issues.append("missing_current_action")
        elif action.agenda_id != agenda.agenda_id:
            issues.append("current_action_wrong_agenda")
        elif action.status not in {"pending", "active"}:
            issues.append("current_action_not_actionable")
        return issues
