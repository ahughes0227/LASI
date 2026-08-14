"""Tests for durable OpenCode-controlled assignment administration."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest
from services.admin import (
    AssignmentAdminService,
    OpenCodeRuntimeError,
    OpenCodeUINotifier,
    ProjectRunner,
    open_admin_service,
)
from services.admin.runner import _internal_coordinator_environment
from services.contracts import (
    CoordinatorDirective,
    ResearchAction,
    ResearchAssignment,
    ResearchLoopPolicy,
)
from services.memory import ActionUsage, AssignmentEvent


class FakeInvoker:
    def __init__(self, directives: Iterable[CoordinatorDirective | Exception]) -> None:
        self.directives = iter(directives)

    def invoke(
        self, assignment: ResearchAssignment, events: list[AssignmentEvent]
    ) -> CoordinatorDirective:
        value = next(self.directives)
        if isinstance(value, Exception):
            raise value
        return value


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


def _directive(assignment_id: str, action: str, **changes: object) -> CoordinatorDirective:
    current_action_id = f"{assignment_id}:initial-plan"
    values: dict[str, object] = {
        "directive_id": f"directive-{action}",
        "assignment_id": assignment_id,
        "action": action,
        "summary": f"{action} summary",
        "progress_made": action != "escalate",
        "current_action_id": current_action_id,
        "completed_action_ids": [current_action_id] if action in {"complete"} else [],
    }
    if action == "escalate":
        values.update(
            escalation_necessity="essential",
            alternatives_considered=[
                {
                    "description": "keep all data local",
                    "feasible": False,
                    "authorized": True,
                    "rejection_reason": "the requested operation cannot run locally",
                }
            ],
        )
    values.update(changes)
    return CoordinatorDirective(**values)


def test_runner_repeatedly_invokes_coordinator_until_complete(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    initial_action_id = f"{assignment_id}:initial-plan"
    review_action = ResearchAction(
        action_id=f"{assignment_id}:review",
        project_id="project-1",
        action_type="evidence_review",
        description="Review the bounded evidence and close the assignment.",
        sequence=1,
    )
    runner = ProjectRunner(
        admin.memory,
        FakeInvoker(
            [
                _directive(
                    assignment_id,
                    "continue",
                    completed_action_ids=[initial_action_id],
                    next_action=review_action,
                ),
                _directive(
                    assignment_id,
                    "complete",
                    current_action_id=review_action.action_id,
                    completed_action_ids=[review_action.action_id],
                ),
            ]
        ),
        notifier=OpenCodeUINotifier(admin.workspace),
    )

    assert runner.run(assignment_id) == "complete"
    status = admin.status(assignment_id)
    assert status.assignment.status == "completed"
    assert status.assignment.orchestrator_turns == 2
    assert not status.worker_active


def test_pause_resume_and_cancel_are_durable_admin_operations(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    assert admin.pause(assignment_id).assignment.status == "paused"
    resumed = admin.resume(assignment_id, launch_worker=False).assignment
    assert resumed.status == "active"
    assert resumed.latest_summary == "Assignment resumed; coordinator turn pending."
    assert admin.cancel(assignment_id).assignment.status == "cancelled"


def test_escalation_waits_for_matching_human_response(admin: AssignmentAdminService) -> None:
    assignment_id = _start(admin)
    runner = ProjectRunner(
        admin.memory,
        FakeInvoker(
            [
                _directive(
                    assignment_id,
                    "escalate",
                    escalation_id="esc-1",
                    escalation_question="May raw data leave the boundary?",
                )
            ]
        ),
        notifier=OpenCodeUINotifier(admin.workspace),
    )
    assert runner.run(assignment_id) == "escalate"
    assert admin.status(assignment_id).assignment.status == "escalated"
    notification = admin.workspace / ".lasi" / "notifications" / "esc-1.json"
    assert notification.exists()
    assert "/lasi-feedback" in notification.read_text()
    assert admin.events(assignment_id)[-1].event_type == ("escalation_ui_notification_published")

    with pytest.raises(ValueError, match="lasi-feedback"):
        admin.resume(assignment_id, launch_worker=False)

    with pytest.raises(ValueError, match="does not match"):
        admin.respond(
            assignment_id,
            escalation_id="wrong",
            response="No",
            launch_worker=False,
        )
    resumed = admin.respond(
        assignment_id,
        escalation_id="esc-1",
        response="No; find a local alternative.",
        launch_worker=False,
    )
    assert resumed.assignment.status == "active"
    assert resumed.assignment.human_response == "No; find a local alternative."
    assert not notification.exists()


def test_resume_refuses_to_replace_an_active_worker(admin: AssignmentAdminService) -> None:
    assignment_id = _start(admin)
    runner = ProjectRunner(admin.memory, FakeInvoker([]))
    assert runner._acquire(assignment_id)

    with pytest.raises(ValueError, match="still active"):
        admin.resume(assignment_id, launch_worker=False)

    runner._release(assignment_id)


def test_three_coordinator_failures_become_structured_failure(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    runner = ProjectRunner(
        admin.memory,
        FakeInvoker([RuntimeError("bad turn"), RuntimeError("bad turn"), RuntimeError("bad turn")]),
    )

    assert runner.run(assignment_id) == "failed"
    status = admin.status(assignment_id).assignment
    assert status.status == "failed"
    assert status.consecutive_orchestrator_errors == 3
    assert [event.event_type for event in admin.events(assignment_id)].count(
        "coordinator_error"
    ) == 3


def test_runtime_failure_blocks_immediately_without_consuming_retries(
    admin: AssignmentAdminService,
) -> None:
    assignment_id = _start(admin)
    runner = ProjectRunner(
        admin.memory,
        FakeInvoker([OpenCodeRuntimeError("CLI missing")]),
    )

    assert runner.run(assignment_id) == "runtime_blocked"
    status = admin.status(assignment_id).assignment
    assert status.status == "runtime_blocked"
    assert status.consecutive_orchestrator_errors == 0
    assert status.orchestrator_turns == 0
    assert admin.events(assignment_id)[-1].event_type == "assignment_runtime_blocked"


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


def test_internal_coordinator_is_promoted_only_in_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OPENCODE_CONFIG_CONTENT",
        '{"agent":{"another-agent":{"mode":"subagent"}},"share":"disabled"}',
    )

    environment = _internal_coordinator_environment()
    inline = json.loads(environment["OPENCODE_CONFIG_CONTENT"])

    assert inline["default_agent"] == "lasi-coordinator"
    assert inline["agent"]["lasi-coordinator"]["mode"] == "primary"
    assert inline["agent"]["another-agent"]["mode"] == "subagent"
    assert inline["share"] == "disabled"
    assert environment["LASI_INTERNAL_COORDINATOR"] == "1"


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
