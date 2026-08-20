"""Retry pacing and concurrent leasing.

Both properties were assumed rather than tested. A failing task returned to `ready` in
the same transaction that rejected it, and every existing test leased as a single owner,
so fan-out was architecturally supported and entirely unproven.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from services.admin import AssignmentAdminService, open_admin_service
from services.contracts import AgentResult, ResearchLoopPolicy
from services.memory.models import RuntimeTaskRecord, TaskEventRecord
from services.runtime.task_runtime import (
    RETRY_BACKOFF_BASE_SECONDS,
    RETRY_BACKOFF_MAX_SECONDS,
    TaskRuntimeError,
    TaskRuntimeService,
    retry_delay_seconds,
)


@pytest.fixture
def admin(tmp_path: Path) -> AssignmentAdminService:
    return open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )


@pytest.fixture
def assignment(admin: AssignmentAdminService) -> str:
    return admin.start(
        project_id="semantic-project",
        objective="prove retries are paced and leases are exclusive",
        loop_policy=ResearchLoopPolicy(
            objective_metric="rmsle", objective_direction="minimize", max_agent_turns=20
        ),
        launch_worker=False,
    ).assignment.assignment_id


def _fail_once(runtime: TaskRuntimeService, assignment_id: str, *, owner: str = "runtime-1"):
    leased = runtime.lease_ready_task(assignment_id, lease_owner=owner)
    assert leased is not None
    runtime.submit_result(
        AgentResult(
            task_id=leased.task.task_id,
            attempt_id=leased.attempt_id,
            status="failed",
            summary="The agent returned no usable result.",
            criterion_results=[],
            failure_reason="agent_error",
        ),
        lease_owner=owner,
    )
    return leased


def test_backoff_grows_and_is_bounded() -> None:
    assert retry_delay_seconds(1) == RETRY_BACKOFF_BASE_SECONDS
    assert retry_delay_seconds(2) == RETRY_BACKOFF_BASE_SECONDS * 2
    assert retry_delay_seconds(3) == RETRY_BACKOFF_BASE_SECONDS * 4
    # Past a few minutes a task is waiting for a human, not for a transient.
    assert retry_delay_seconds(50) == RETRY_BACKOFF_MAX_SECONDS


def test_a_failed_task_is_not_immediately_releasable(
    admin: AssignmentAdminService, assignment: str
) -> None:
    """The defect this exists for: three attempts burned in milliseconds."""
    runtime = TaskRuntimeService(admin.memory)
    _fail_once(runtime, assignment)

    assert runtime.lease_ready_task(assignment, lease_owner="runtime-1") is None


def test_the_retry_becomes_available_once_the_delay_passes(
    admin: AssignmentAdminService, assignment: str
) -> None:
    runtime = TaskRuntimeService(admin.memory)
    _fail_once(runtime, assignment)

    later = datetime.now(UTC) + timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS + 1)

    assert runtime.lease_ready_task(assignment, lease_owner="runtime-1", now=later) is not None


def test_the_delay_is_recorded_with_the_retry_event(
    admin: AssignmentAdminService, assignment: str
) -> None:
    """A pause nobody can see is indistinguishable from a stall."""
    runtime = TaskRuntimeService(admin.memory)
    leased = _fail_once(runtime, assignment)

    with admin.memory.read_session() as session:
        task = session.get(RuntimeTaskRecord, leased.task.task_id)
        assert task is not None
        assert task.next_eligible_at is not None

        retry_events = [
            event
            for event in session.query(TaskEventRecord)
            .filter(TaskEventRecord.task_id == leased.task.task_id)
            .all()
            if event.event_type == "task_retry_ready"
        ]

    assert len(retry_events) == 1
    assert retry_events[0].payload["retry_delay_seconds"] == RETRY_BACKOFF_BASE_SECONDS


def test_a_task_that_never_failed_is_eligible_immediately(
    admin: AssignmentAdminService, assignment: str
) -> None:
    runtime = TaskRuntimeService(admin.memory)

    leased = runtime.lease_ready_task(assignment, lease_owner="runtime-1")

    assert leased is not None
    with admin.memory.read_session() as session:
        task = session.get(RuntimeTaskRecord, leased.task.task_id)
        assert task is not None
        # Null means eligible now; a fresh task waits on nothing.
        assert task.next_eligible_at is None


def test_two_owners_cannot_hold_the_same_task(
    admin: AssignmentAdminService, assignment: str
) -> None:
    """Fan-out was supported and unproven; every prior test leased as one owner."""
    runtime = TaskRuntimeService(admin.memory)

    first = runtime.lease_ready_task(assignment, lease_owner="runtime-1")
    second = runtime.lease_ready_task(assignment, lease_owner="runtime-2")

    assert first is not None
    # Only one task is ready at bootstrap, and it is already leased.
    assert second is None


def test_a_result_from_the_wrong_owner_is_refused(
    admin: AssignmentAdminService, assignment: str
) -> None:
    """A second worker must not be able to submit against another's lease."""
    runtime = TaskRuntimeService(admin.memory)
    leased = runtime.lease_ready_task(assignment, lease_owner="runtime-1")
    assert leased is not None

    with pytest.raises(TaskRuntimeError, match="active task lease"):
        runtime.submit_result(
            AgentResult(
                task_id=leased.task.task_id,
                attempt_id=leased.attempt_id,
                status="failed",
                summary="submitted by a worker that does not hold the lease",
                criterion_results=[],
                failure_reason="agent_error",
            ),
            lease_owner="runtime-2",
        )
