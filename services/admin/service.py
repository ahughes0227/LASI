"""Durable lifecycle operations exposed only through LASI OpenCode commands."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from sqlalchemy import select

from services.contracts import ResearchAssignment, ResearchLoopPolicy
from services.memory import (
    AssignmentEvent,
    Base,
    OperationalMemory,
    Project,
    ResearchAssignmentRecord,
    create_engine,
    create_session_factory,
)

from .notifications import OpenCodeUINotifier
from .runner import validate_opencode_runtime

_TERMINAL = frozenset({"cancelled", "completed", "failed"})


@dataclass(frozen=True)
class AssignmentStatus:
    assignment: ResearchAssignment
    next_wake_at: datetime | None = None
    worker_active: bool = False


class AssignmentAdminService:
    """Single lifecycle authority for start/status/pause/resume/cancel/respond."""

    def __init__(self, memory: OperationalMemory, *, database_url: str, workspace: Path) -> None:
        self.memory = memory
        self.database_url = database_url
        self.workspace = workspace.resolve()

    def start(
        self,
        *,
        project_id: str,
        objective: str,
        loop_policy: ResearchLoopPolicy,
        project_name: str | None = None,
        problem_type: str = "unknown",
        modality: str = "unknown",
        launch_worker: bool = True,
    ) -> AssignmentStatus:
        if not objective.strip():
            raise ValueError("assignment objective must not be empty")
        if launch_worker:
            validate_opencode_runtime()
        now = datetime.now(UTC)
        assignment_id = f"assignment-{uuid4().hex}"
        with self.memory.transaction() as session:
            existing = session.scalar(
                select(ResearchAssignmentRecord).where(
                    ResearchAssignmentRecord.project_id == project_id,
                    ResearchAssignmentRecord.status.not_in(tuple(_TERMINAL)),
                )
            )
            if existing is not None:
                raise ValueError(f"project already has active assignment: {existing.assignment_id}")
            if session.get(Project, project_id) is None:
                session.add(
                    Project(
                        project_id=project_id,
                        project_name=project_name or project_id,
                        problem_type=problem_type,
                        modality=modality,
                    )
                )
            contract = ResearchAssignment(
                assignment_id=assignment_id,
                project_id=project_id,
                objective=objective,
                loop_policy=loop_policy,
                created_at=now,
                updated_at=now,
            )
            session.add(
                ResearchAssignmentRecord(
                    assignment_id=assignment_id,
                    project_id=project_id,
                    objective=objective,
                    status="active",
                    payload=contract.model_dump(mode="json"),
                )
            )
            # These models intentionally have no ORM relationships: ordering is
            # explicit so the event's foreign keys always reference flushed rows.
            session.flush()
            session.add(_event(contract, "assignment_started"))
        if launch_worker:
            self.launch_worker(assignment_id)
        return self.status(assignment_id)

    def status(self, identifier: str) -> AssignmentStatus:
        record = self._resolve(identifier)
        return AssignmentStatus(
            assignment=_contract(record),
            next_wake_at=record.next_wake_at,
            worker_active=bool(
                record.lease_expires_at and record.lease_expires_at >= datetime.now(UTC)
            ),
        )

    def pause(self, identifier: str) -> AssignmentStatus:
        record = self._resolve(identifier)
        if record.status in _TERMINAL:
            raise ValueError(f"cannot pause terminal assignment: {record.status}")
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.pause_requested = True
            current.status = "paused" if not _lease_active(current, now) else "pausing"
            _update_payload(current, status=current.status, pause_requested=True, now=now)
            session.add(_event(_contract(current), "pause_requested"))
        return self.status(record.assignment_id)

    def resume(self, identifier: str, *, launch_worker: bool = True) -> AssignmentStatus:
        record = self._resolve(identifier)
        if launch_worker:
            validate_opencode_runtime()
        now = datetime.now(UTC)
        if record.status == "escalated":
            raise ValueError("answer the pending escalation with lasi-feedback")
        if _lease_active(record, now):
            raise ValueError("assignment worker is still active")
        if record.status not in {
            "paused",
            "pausing",
            "waiting",
            "failed",
            "runtime_blocked",
            "active",
        }:
            raise ValueError(f"assignment cannot be resumed from {record.status}")
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.pause_requested = False
            current.cancel_requested = False
            current.status = "active"
            current.consecutive_orchestrator_errors = 0
            current.lease_owner = None
            current.lease_expires_at = None
            _update_payload(
                current,
                status="active",
                pause_requested=False,
                consecutive_orchestrator_errors=0,
                latest_summary="Assignment resumed; coordinator turn pending.",
                now=now,
            )
            session.add(_event(_contract(current), "assignment_resumed"))
        if launch_worker:
            self.launch_worker(record.assignment_id)
        return self.status(record.assignment_id)

    def cancel(self, identifier: str) -> AssignmentStatus:
        record = self._resolve(identifier)
        if record.status in _TERMINAL:
            return self.status(record.assignment_id)
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.cancel_requested = True
            current.status = "cancelling" if _lease_active(current, now) else "cancelled"
            _update_payload(current, status=current.status, cancel_requested=True, now=now)
            session.add(_event(_contract(current), "cancel_requested"))
        return self.status(record.assignment_id)

    def respond(
        self, identifier: str, *, escalation_id: str, response: str, launch_worker: bool = True
    ) -> AssignmentStatus:
        record = self._resolve(identifier)
        contract = _contract(record)
        if record.status != "escalated" or contract.pending_escalation_id != escalation_id:
            raise ValueError("response does not match the pending escalation")
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.status = "active"
            current.pending_escalation_id = None
            value = _contract(current).model_copy(
                update={
                    "status": "active",
                    "pending_escalation_id": None,
                    "pending_escalation_question": None,
                    "human_response": response,
                    "updated_at": now,
                }
            )
            current.payload = value.model_dump(mode="json")
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=current.assignment_id,
                    project_id=current.project_id,
                    event_type="escalation_answered",
                    payload={"escalation_id": escalation_id, "response": response},
                )
            )
        OpenCodeUINotifier(self.workspace).clear_escalation(escalation_id)
        if launch_worker:
            self.launch_worker(record.assignment_id)
        return self.status(record.assignment_id)

    def events(self, identifier: str) -> list[AssignmentEvent]:
        record = self._resolve(identifier)
        with self.memory._session_factory() as session:
            return list(
                session.scalars(
                    select(AssignmentEvent)
                    .where(AssignmentEvent.assignment_id == record.assignment_id)
                    .order_by(AssignmentEvent.created_at, AssignmentEvent.event_id)
                )
            )

    def launch_worker(self, assignment_id: str) -> int:
        validate_opencode_runtime()
        log_dir = self.workspace / ".lasi" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{assignment_id}.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(  # noqa: S603 - fixed internal module invocation.
                [
                    sys.executable,
                    "-m",
                    "services.admin.worker",
                    "--database-url",
                    self.database_url,
                    "--workspace",
                    str(self.workspace),
                    "--assignment-id",
                    assignment_id,
                ],
                cwd=self.workspace,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        return process.pid

    def _resolve(self, identifier: str) -> ResearchAssignmentRecord:
        with self.memory._session_factory() as session:
            direct = session.get(ResearchAssignmentRecord, identifier)
            if direct is not None:
                return cast(ResearchAssignmentRecord, direct)
            matches = cast(
                list[ResearchAssignmentRecord],
                list(
                    session.scalars(
                        select(ResearchAssignmentRecord)
                        .where(ResearchAssignmentRecord.project_id == identifier)
                        .order_by(ResearchAssignmentRecord.created_at.desc())
                    )
                ),
            )
            if not matches:
                raise KeyError(f"assignment or project not found: {identifier}")
            return matches[0]


def open_admin_service(
    *, database_url: str | None = None, workspace: str | Path | None = None
) -> AssignmentAdminService:
    configured_workspace = workspace or os.environ.get("LASI_WORKSPACE")
    root = Path(configured_workspace) if configured_workspace is not None else Path.cwd()
    root = root.resolve()
    default_db = root / ".lasi" / "operational.sqlite3"
    default_db.parent.mkdir(parents=True, exist_ok=True)
    url = database_url or os.environ.get("LASI_DATABASE_URL", f"sqlite:///{default_db}")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return AssignmentAdminService(
        OperationalMemory(create_session_factory(engine)), database_url=url, workspace=root
    )


def _contract(record: ResearchAssignmentRecord) -> ResearchAssignment:
    return ResearchAssignment.model_validate(record.payload)


def _event(assignment: ResearchAssignment, event_type: str) -> AssignmentEvent:
    return AssignmentEvent(
        event_id=f"assignment-event-{uuid4().hex}",
        assignment_id=assignment.assignment_id,
        project_id=assignment.project_id,
        event_type=event_type,
        payload=assignment.model_dump(mode="json"),
    )


def _lease_active(record: ResearchAssignmentRecord, now: datetime) -> bool:
    return bool(record.lease_expires_at and record.lease_expires_at >= now)


def _update_payload(record: ResearchAssignmentRecord, *, now: datetime, **updates: object) -> None:
    record.payload = (
        _contract(record).model_copy(update={**updates, "updated_at": now}).model_dump(mode="json")
    )
