"""Tests for durable OpenCode-controlled assignment administration."""

from __future__ import annotations

from pathlib import Path

import pytest
from services.admin import (
    AssignmentAdminService,
    OpenCodeRuntimeError,
    OpenCodeUINotifier,
    open_admin_service,
)
from services.contracts import ResearchLoopPolicy
from services.memory import ActionUsage, AssignmentEvent, ResearchAssignmentRecord


@pytest.fixture
def admin(tmp_path: Path) -> AssignmentAdminService:
    return open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )


def _policy() -> ResearchLoopPolicy:
    return ResearchLoopPolicy(objective_metric="score", objective_direction="maximize")


def _start(admin: AssignmentAdminService) -> str:
    return admin.start(
        project_id="project-1",
        objective="maximize the valid score",
        loop_policy=_policy(),
        launch_worker=False,
    ).assignment.assignment_id


def _escalate(admin: AssignmentAdminService, assignment_id: str, escalation_id: str) -> None:
    """Put the assignment into the state the task runtime records on escalation."""
    with admin.memory.transaction() as session:
        record = session.get(ResearchAssignmentRecord, assignment_id)
        assert record is not None
        record.status = "escalated"
        record.pending_escalation_id = escalation_id
        record.payload = {
            **record.payload,
            "status": "escalated",
            "pending_escalation_id": escalation_id,
            "pending_escalation_question": "May raw data leave the boundary?",
        }


def test_start_creates_an_assignment_without_an_agenda(admin: AssignmentAdminService) -> None:
    assignment = admin.start(
        project_id="project-1",
        objective="maximize the valid score",
        loop_policy=_policy(),
        launch_worker=False,
    ).assignment

    assert assignment.status == "active"
    # The task graph, not a second agenda plane, is what a proposal is versioned
    # against.  Bootstrapping the orchestration task advances it past its start.
    assert assignment.graph_revision == 2
    assert not hasattr(assignment, "agenda_id")


def test_pause_resume_and_cancel_are_durable_admin_operations(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    assert admin.pause(assignment_id).assignment.status == "paused"
    resumed = admin.resume(assignment_id, launch_worker=False).assignment
    assert resumed.status == "active"
    assert admin.cancel(assignment_id).assignment.status == "cancelled"


def test_escalation_waits_for_matching_human_response(admin: AssignmentAdminService) -> None:
    assignment_id = _start(admin)
    _escalate(admin, assignment_id, "esc-1")

    status = admin.status(assignment_id).assignment
    assert status.status == "escalated"
    notification = OpenCodeUINotifier(admin.workspace).publish_escalation(status)
    assert "/lasi-feedback" in notification.read_text()

    with pytest.raises(ValueError, match="lasi-feedback"):
        admin.resume(assignment_id, launch_worker=False)
    with pytest.raises(ValueError, match="does not match"):
        admin.respond(assignment_id, escalation_id="wrong", response="No", launch_worker=False)

    resumed = admin.respond(
        assignment_id,
        escalation_id="esc-1",
        response="No; find a local alternative.",
        launch_worker=False,
    )
    assert resumed.assignment.status == "active"
    assert resumed.assignment.human_response == "No; find a local alternative."
    assert not notification.exists()


def test_notifier_refuses_an_assignment_that_is_not_escalated(
    admin: AssignmentAdminService,
) -> None:
    """The assignment record is the only place an escalation may be declared."""
    assignment_id = _start(admin)
    status = admin.status(assignment_id).assignment

    with pytest.raises(ValueError, match="only an escalated assignment"):
        OpenCodeUINotifier(admin.workspace).publish_escalation(status)


def test_start_preflights_runtime_before_creating_assignment(
    admin: AssignmentAdminService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LASI_OPENCODE_EXECUTABLE", "definitely-not-an-opencode-binary")

    with pytest.raises(OpenCodeRuntimeError, match="not found on PATH"):
        admin.start(
            project_id="preflight-project",
            objective="do not create this assignment",
            loop_policy=_policy(),
        )
    with pytest.raises(KeyError):
        admin.status("preflight-project")


def test_state_survives_service_reopen(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'operational.sqlite3'}"
    first = open_admin_service(database_url=database_url, workspace=tmp_path)
    assignment_id = _start(first)
    first.pause(assignment_id)

    reopened = open_admin_service(database_url=database_url, workspace=tmp_path)
    assert reopened.status(assignment_id).assignment.status == "paused"


def test_service_reopen_marks_legacy_coordinator_usage_gap_once(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'operational.sqlite3'}"
    first = open_admin_service(database_url=database_url, workspace=tmp_path)
    assignment_id = _start(first)
    first.memory.add(
        AssignmentEvent(
            event_id="legacy-coordinator-event",
            assignment_id=assignment_id,
            project_id="project-1",
            event_type="coordinator_continue",
            payload={"directive_id": "legacy-directive"},
        )
    )
    first.memory.add(
        AssignmentEvent(
            event_id="legacy-coordinator-error",
            assignment_id=assignment_id,
            project_id="project-1",
            event_type="coordinator_error",
            payload={"error": "historical runtime failure"},
        )
    )

    reopened = open_admin_service(database_url=database_url, workspace=tmp_path)
    receipt = reopened.memory.get(ActionUsage, "usage-legacy-legacy-coordinator-event")
    assert receipt is not None
    assert receipt.action_id == "legacy-directive"
    assert receipt.metering_status == "not_available"
    assert "cannot be reconstructed" in receipt.unavailable_reason
    error_receipt = reopened.memory.get(ActionUsage, "usage-legacy-legacy-coordinator-error")
    assert error_receipt is not None
    assert error_receipt.metering_status == "not_available"

    open_admin_service(database_url=database_url, workspace=tmp_path)
    records = reopened.memory.list_for_project(ActionUsage, "project-1")
    assert [record.action_usage_id for record in records].count(
        "usage-legacy-legacy-coordinator-event"
    ) == 1


def test_only_one_nonterminal_assignment_is_allowed_per_project(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    with pytest.raises(ValueError, match="already has active assignment"):
        _start(admin)
    admin.cancel(assignment_id)
    assert _start(admin) != assignment_id
