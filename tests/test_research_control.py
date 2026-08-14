"""Regression coverage for the Mercury plan-following failure."""

import pytest
from services.admin import AssignmentAdminService, open_admin_service
from services.contracts import (
    CoordinatorDirective,
    ResearchAction,
    ResearchLoopPolicy,
)
from services.memory import ResearchActionRecord, ResearchAgendaRecord
from services.workflows.research_control import ResearchControlError, ResearchControlService


def _admin(tmp_path) -> AssignmentAdminService:
    return open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )


def _start(admin: AssignmentAdminService) -> str:
    return admin.start(
        project_id="mercury",
        objective="diagnose the remaining forecast error",
        loop_policy=ResearchLoopPolicy(objective_metric="rmsle", objective_direction="minimize"),
        launch_worker=False,
    ).assignment.assignment_id


def test_mercury_replay_rejects_component_work_when_error_analysis_is_required(
    tmp_path,
) -> None:
    admin = _admin(tmp_path)
    assignment_id = _start(admin)
    required = ResearchAction(
        action_id="MERCURY-ACTION-ERROR-ANALYSIS-0002",
        project_id="mercury",
        action_type="error_analysis",
        description="Bucket holdout errors by target regime, family, and horizon.",
        sequence=1,
    )
    with admin.memory.transaction() as session:
        agenda = session.query(ResearchAgendaRecord).filter_by(assignment_id=assignment_id).one()
        initial = session.get(ResearchActionRecord, agenda.current_action_id)
        assert initial is not None
        initial.status = "completed"
        initial.payload = {**initial.payload, "status": "completed"}
        session.add(
            ResearchActionRecord(
                action_id=required.action_id,
                agenda_id=agenda.agenda_id,
                project_id="mercury",
                action_type=required.action_type,
                status="pending",
                sequence=1,
                payload=required.model_dump(mode="json"),
            )
        )
        agenda.current_action_id = required.action_id
        agenda.payload = {**agenda.payload, "current_action_id": required.action_id}

    wrong = CoordinatorDirective(
        directive_id="mercury-hurdle-diversion",
        assignment_id=assignment_id,
        action="continue",
        summary="build a hurdle component",
        progress_made=True,
        current_action_id="MERCURY-ACTION-HURDLE-COMPONENT",
    )
    with admin.memory._session_factory() as session:
        with pytest.raises(ResearchControlError, match="required current action"):
            ResearchControlService().validate(session, assignment_id, wrong)


def test_escalation_is_rejected_while_authorized_local_alternative_remains(tmp_path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _start(admin)
    directive = CoordinatorDirective(
        directive_id="remote-escalation",
        assignment_id=assignment_id,
        action="escalate",
        summary="request remote containment",
        progress_made=False,
        current_action_id=f"{assignment_id}:initial-plan",
        escalation_id="esc-remote",
        escalation_question="Provide a remote host?",
        escalation_necessity="essential",
        alternatives_considered=[
            {
                "description": "run deterministic local error analysis",
                "feasible": True,
                "authorized": True,
            }
        ],
    )
    with admin.memory._session_factory() as session:
        with pytest.raises(ResearchControlError, match="alternative remains"):
            ResearchControlService().validate(session, assignment_id, directive)
