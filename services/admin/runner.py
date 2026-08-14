"""Event-driven project runner that invokes ephemeral OpenCode coordinator turns."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select

from services.contracts import CoordinatorDirective, ResearchAssignment
from services.memory import AssignmentEvent, OperationalMemory, ResearchAssignmentRecord
from services.workflows.research_control import ResearchControlError, ResearchControlService

from .notifications import OpenCodeUINotifier

_DIRECTIVE = re.compile(r"<LASI_DIRECTIVE>\s*(\{.*?\})\s*</LASI_DIRECTIVE>", re.DOTALL)


class CoordinatorInvoker(Protocol):
    def invoke(
        self, assignment: ResearchAssignment, events: list[AssignmentEvent]
    ) -> CoordinatorDirective: ...


class OpenCodeRuntimeError(RuntimeError):
    """Non-retryable local infrastructure failure before a coordinator turn."""


def resolve_opencode_executable(executable: str | None = None) -> str:
    configured = executable or os.environ.get("LASI_OPENCODE_EXECUTABLE", "opencode")
    resolved = shutil.which(configured)
    if resolved is None:
        raise OpenCodeRuntimeError(
            f"OpenCode CLI is unavailable: {configured!r} was not found on PATH"
        )
    return resolved


def validate_opencode_runtime(executable: str | None = None) -> str:
    """Verify the CLI and its non-interactive run command before launching work."""
    resolved = resolve_opencode_executable(executable)
    try:
        completed = subprocess.run(  # noqa: S603 - resolved executable, no shell.
            [resolved, "run", "--help"],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OpenCodeRuntimeError(f"OpenCode CLI preflight failed: {exc}") from exc
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0 or "opencode run" not in output.lower():
        detail = output.strip()[-1000:]
        raise OpenCodeRuntimeError(
            f"OpenCode CLI does not provide an operational run command: {detail}"
        )
    return resolved


class OpenCodeCoordinatorInvoker:
    """Invoke one fresh internal coordinator turn through OpenCode's supported CLI."""

    def __init__(self, workspace: Path, *, executable: str | None = None) -> None:
        self.workspace = workspace.resolve()
        self.executable = executable or os.environ.get("LASI_OPENCODE_EXECUTABLE", "opencode")

    def invoke(
        self, assignment: ResearchAssignment, events: list[AssignmentEvent]
    ) -> CoordinatorDirective:
        executable = validate_opencode_runtime(self.executable)
        prompt = _coordinator_prompt(assignment, events)
        environment = _internal_coordinator_environment()
        completed = subprocess.run(  # noqa: S603 - resolved OpenCode executable, no shell.
            [
                executable,
                "run",
                "--agent",
                "lasi-coordinator",
                "--format",
                "json",
                "--auto",
                "--dir",
                str(self.workspace),
                "--title",
                f"LASI {assignment.assignment_id} turn {assignment.orchestrator_turns + 1}",
                prompt,
            ],
            cwd=self.workspace,
            text=True,
            capture_output=True,
            timeout=3600,
            check=False,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"OpenCode coordinator failed ({completed.returncode}): {completed.stderr[-1000:]}"
            )
        text = _event_text(completed.stdout)
        matches = list(_DIRECTIVE.finditer(text))
        if not matches:
            raise ValueError(
                "coordinator response did not contain a LASI directive; "
                f"response tail: {text[-1000:]}"
            )
        return CoordinatorDirective.model_validate_json(matches[-1].group(1))


class ProjectRunner:
    """Own wakeups and repeated coordinator turns until a terminal/waiting boundary."""

    def __init__(
        self,
        memory: OperationalMemory,
        invoker: CoordinatorInvoker,
        *,
        lease_seconds: int = 30,
        max_consecutive_errors: int = 3,
        notifier: OpenCodeUINotifier | None = None,
    ) -> None:
        self.memory = memory
        self.invoker = invoker
        self.lease_seconds = lease_seconds
        self.max_consecutive_errors = max_consecutive_errors
        self.notifier = notifier
        self.worker_id = f"worker-{uuid4().hex}"

    def run(self, assignment_id: str) -> str:
        if not self._acquire(assignment_id):
            return "already_running"
        try:
            while True:
                record = self.memory.get(ResearchAssignmentRecord, assignment_id)
                if record is None:
                    raise KeyError(f"assignment not found: {assignment_id}")
                if record.cancel_requested:
                    self._transition(record, "cancelled", "assignment_cancelled")
                    return "cancelled"
                if record.pause_requested:
                    self._transition(record, "paused", "assignment_paused")
                    return "paused"
                if record.status in {"cancelled", "completed", "escalated", "failed", "paused"}:
                    return record.status
                now = datetime.now(UTC)
                if record.next_wake_at and record.next_wake_at > now:
                    self._renew(record.assignment_id)
                    time.sleep(min(2.0, (record.next_wake_at - now).total_seconds()))
                    continue
                assignment = ResearchAssignment.model_validate(record.payload)
                try:
                    directive = self._invoke_with_heartbeat(
                        assignment, self._recent_events(assignment_id, limit=30)
                    )
                    if directive.assignment_id != assignment_id:
                        raise ValueError("coordinator directive belongs to another assignment")
                except OpenCodeRuntimeError as exc:
                    self._block_runtime(record, str(exc))
                    return "runtime_blocked"
                except Exception as exc:  # coordinator failures are retryable operational evidence.
                    failures = record.consecutive_orchestrator_errors + 1
                    if failures >= self.max_consecutive_errors:
                        self._fail(record, str(exc), failures)
                        return "failed"
                    self._record_error(record, str(exc), failures)
                    time.sleep(min(5.0, float(failures)))
                    continue
                try:
                    result = self._apply(record, directive)
                except ResearchControlError as exc:
                    failures = record.consecutive_orchestrator_errors + 1
                    if failures >= self.max_consecutive_errors:
                        self._fail(record, str(exc), failures)
                        return "failed"
                    self._record_error(record, str(exc), failures)
                    continue
                if result != "continue":
                    return result
        finally:
            self._release(assignment_id)

    def _apply(self, record: ResearchAssignmentRecord, directive: CoordinatorDirective) -> str:
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            control = ResearchControlService()
            issues = control.audit(session, current.assignment_id)
            if issues:
                raise ResearchControlError(
                    "research state consistency check failed: " + ", ".join(issues)
                )
            control.validate(session, current.assignment_id, directive)
            agenda_action = control.apply(session, current.assignment_id, directive)
            current.orchestrator_turns += 1
            current.consecutive_orchestrator_errors = 0
            current.next_wake_at = None
            contract = ResearchAssignment.model_validate(current.payload)
            updates: dict[str, object] = {
                "orchestrator_turns": current.orchestrator_turns,
                "consecutive_orchestrator_errors": 0,
                "latest_summary": directive.summary,
                "updated_at": now,
                "human_response": None,
                "current_action_id": agenda_action.action_id,
                "current_action": agenda_action,
            }
            if directive.action == "complete":
                current.status = "completed"
                updates["status"] = "completed"
            elif directive.action == "escalate":
                current.status = "escalated"
                current.pending_escalation_id = directive.escalation_id
                updates.update(
                    status="escalated",
                    pending_escalation_id=directive.escalation_id,
                    pending_escalation_question=directive.escalation_question,
                )
            elif directive.action == "wait":
                current.status = "waiting"
                seconds = directive.wait_seconds or 5
                current.next_wake_at = now + timedelta(seconds=seconds)
                updates["status"] = "waiting"
            else:
                current.status = "active"
                updates["status"] = "active"
            current.payload = contract.model_copy(update=updates).model_dump(mode="json")
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=current.assignment_id,
                    project_id=current.project_id,
                    event_type=f"coordinator_{directive.action}",
                    payload=directive.model_dump(mode="json"),
                )
            )
        if directive.action == "escalate" and self.notifier is not None:
            self._publish_escalation(record.assignment_id, directive)
        return "continue" if directive.action in {"continue", "wait"} else directive.action

    def _publish_escalation(self, assignment_id: str, directive: CoordinatorDirective) -> None:
        assignment_record = self.memory.get(ResearchAssignmentRecord, assignment_id)
        assert assignment_record is not None
        assignment = ResearchAssignment.model_validate(assignment_record.payload)
        notifier = self.notifier
        assert notifier is not None
        try:
            path = notifier.publish_escalation(assignment, directive)
            event_type = "escalation_ui_notification_published"
            payload = {"path": str(path), "escalation_id": directive.escalation_id}
        except Exception as exc:
            event_type = "escalation_ui_notification_failed"
            payload = {"message": str(exc), "escalation_id": directive.escalation_id}
        with self.memory.transaction() as session:
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=assignment.assignment_id,
                    project_id=assignment.project_id,
                    event_type=event_type,
                    payload=payload,
                )
            )

    def _invoke_with_heartbeat(
        self, assignment: ResearchAssignment, events: list[AssignmentEvent]
    ) -> CoordinatorDirective:
        """Keep the worker lease alive while an OpenCode turn is executing tools."""
        stopped = threading.Event()

        def heartbeat() -> None:
            interval = max(1.0, self.lease_seconds / 3)
            while not stopped.wait(interval):
                self._renew(assignment.assignment_id)

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            return self.invoker.invoke(assignment, events)
        finally:
            stopped.set()
            thread.join(timeout=1)

    def _acquire(self, assignment_id: str) -> bool:
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            record = session.get(ResearchAssignmentRecord, assignment_id)
            if record is None:
                raise KeyError(f"assignment not found: {assignment_id}")
            if record.lease_expires_at and record.lease_expires_at >= now:
                return False
            record.lease_owner = self.worker_id
            record.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        return True

    def _renew(self, assignment_id: str) -> None:
        with self.memory.transaction() as session:
            record = session.get(ResearchAssignmentRecord, assignment_id)
            if record is not None and record.lease_owner == self.worker_id:
                record.lease_expires_at = datetime.now(UTC) + timedelta(seconds=self.lease_seconds)

    def _release(self, assignment_id: str) -> None:
        with self.memory.transaction() as session:
            record = session.get(ResearchAssignmentRecord, assignment_id)
            if record is not None and record.lease_owner == self.worker_id:
                record.lease_owner = None
                record.lease_expires_at = None

    def _recent_events(self, assignment_id: str, *, limit: int) -> list[AssignmentEvent]:
        with self.memory._session_factory() as session:
            events = list(
                session.scalars(
                    select(AssignmentEvent)
                    .where(AssignmentEvent.assignment_id == assignment_id)
                    .order_by(AssignmentEvent.created_at.desc())
                    .limit(limit)
                )
            )
        return list(reversed(events))

    def _transition(self, record: ResearchAssignmentRecord, status: str, event_type: str) -> None:
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.status = status
            current.payload = (
                ResearchAssignment.model_validate(current.payload)
                .model_copy(update={"status": status, "updated_at": now})
                .model_dump(mode="json")
            )
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=current.assignment_id,
                    project_id=current.project_id,
                    event_type=event_type,
                    payload={"status": status},
                )
            )

    def _record_error(self, record: ResearchAssignmentRecord, message: str, failures: int) -> None:
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.consecutive_orchestrator_errors = failures
            current.payload = (
                ResearchAssignment.model_validate(current.payload)
                .model_copy(
                    update={
                        "consecutive_orchestrator_errors": failures,
                        "latest_summary": f"Coordinator error: {message}",
                        "updated_at": now,
                    }
                )
                .model_dump(mode="json")
            )
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=current.assignment_id,
                    project_id=current.project_id,
                    event_type="coordinator_error",
                    payload={"message": message, "attempt": failures},
                )
            )
        self._renew(record.assignment_id)

    def _fail(self, record: ResearchAssignmentRecord, message: str, failures: int) -> None:
        self._record_error(record, message, failures)
        self._transition(record, "failed", "assignment_failed")

    def _block_runtime(self, record: ResearchAssignmentRecord, message: str) -> None:
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            current = session.get(ResearchAssignmentRecord, record.assignment_id)
            assert current is not None
            current.status = "runtime_blocked"
            current.payload = (
                ResearchAssignment.model_validate(current.payload)
                .model_copy(
                    update={
                        "status": "runtime_blocked",
                        "latest_summary": f"Runtime blocked: {message}",
                        "updated_at": now,
                    }
                )
                .model_dump(mode="json")
            )
            session.add(
                AssignmentEvent(
                    event_id=f"assignment-event-{uuid4().hex}",
                    assignment_id=current.assignment_id,
                    project_id=current.project_id,
                    event_type="assignment_runtime_blocked",
                    payload={"message": message, "retryable_after_preflight": True},
                )
            )


def _coordinator_prompt(assignment: ResearchAssignment, events: list[AssignmentEvent]) -> str:
    event_packet = [
        {"event_type": event.event_type, "created_at": event.created_at, "payload": event.payload}
        for event in events
    ]
    return f"""You are the internal LASI research coordinator for one ephemeral turn.

Read AGENTS.md and reconstruct minimum-sufficient state from durable project
artifacts and the packet below. Progress the assignment using approved tools and
specialist agents. Do not stop merely to report. Before finishing this turn,
return exactly one validated next-action directive between the required tags.

Assignment:
{assignment.model_dump_json(indent=2)}

Recent administrative events:
{json.dumps(event_packet, default=str, indent=2)}

Required final format:
<LASI_DIRECTIVE>
{{"directive_id":"directive-...","assignment_id":"{assignment.assignment_id}","action":"continue|wait|complete|escalate","summary":"...","progress_made":true,"current_action_id":"{assignment.current_action_id}","completed_action_ids":[],"next_action":null,"experiment_plan_id":null,"decision_id":null,"alternatives_considered":[],"escalation_necessity":null,"research_attempt":null,"next_prompt":null,"wait_seconds":null,"escalation_id":null,"escalation_question":null,"evidence_refs":[],"report_refs":[]}}
</LASI_DIRECTIVE>

The assignment's current_action is authoritative. Do not implement or execute a
different action. If execution is needed, persist an ExperimentPlan and an
allowing DecisionRecord first, then reference both. Completing the current
action requires completed_action_ids and either a typed next_action or terminal
completion. Before escalation, evaluate local authorized alternatives; an
escalation is invalid while one remains feasible.

Use `escalate` only for genuine human discretion. Use `continue` when another
coordinator turn should start immediately, `wait` only for running external
work, and `complete` only when the objective or governed plateau condition is
satisfied.
"""


def _internal_coordinator_environment() -> dict[str, str]:
    """Promote the coordinator only inside `opencode run`, never in the user UI."""
    environment = dict(os.environ)
    environment["LASI_INTERNAL_COORDINATOR"] = "1"
    raw = environment.get("OPENCODE_CONFIG_CONTENT")
    try:
        inline = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise OpenCodeRuntimeError("OPENCODE_CONFIG_CONTENT is not valid JSON") from exc
    if not isinstance(inline, dict):
        raise OpenCodeRuntimeError("OPENCODE_CONFIG_CONTENT must be a JSON object")
    agents = inline.setdefault("agent", {})
    if not isinstance(agents, dict):
        raise OpenCodeRuntimeError("inline OpenCode agent configuration must be an object")
    coordinator = agents.setdefault("lasi-coordinator", {})
    if not isinstance(coordinator, dict):
        raise OpenCodeRuntimeError("inline lasi-coordinator configuration must be an object")
    coordinator["mode"] = "primary"
    inline["default_agent"] = "lasi-coordinator"
    environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(inline)
    return environment


def _event_text(raw: str) -> str:
    values: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            values.append(line)
            continue
        values.extend(_text_values(event))
    return "\n".join(values)


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _text_values(child)]
    if isinstance(value, Mapping):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return [str(value["text"])]
        return [item for child in value.values() for item in _text_values(child)]
    return []
