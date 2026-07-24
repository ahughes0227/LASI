"""Application service for current outcomes and append-only outcome events."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import uuid4

from lasi.contracts import ProjectOutcome
from lasi.contracts.models import OutcomeEvent as OutcomeEventContract
from lasi.memory.models import (
    Approval,
    Decision,
)
from lasi.memory.models import (
    Outcome as OutcomeRecord,
)
from lasi.memory.models import (
    OutcomeEvent as OutcomeEventRecord,
)

from .errors import (
    InvalidOutcomeTransition,
    MissingDeploymentApproval,
    MissingProductionEvidence,
    OutcomeNotFound,
    UnknownOutcomeStatus,
)

OUTCOME_STATUSES = frozenset(
    {
        "pending",
        "research_only",
        "validated_not_deployed",
        "deployed",
        "successful_in_production",
        "failed_validation",
        "failed_in_production",
        "cancelled",
        "abandoned",
        "blocked",
        "superseded",
        "archived",
    }
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset(OUTCOME_STATUSES - {"pending", "successful_in_production"}),
    "research_only": frozenset({"archived", "superseded"}),
    "validated_not_deployed": frozenset(
        {"deployed", "cancelled", "abandoned", "superseded", "archived"}
    ),
    "deployed": frozenset(
        {"successful_in_production", "failed_in_production", "archived", "superseded"}
    ),
    "successful_in_production": frozenset({"archived", "superseded"}),
    "failed_validation": frozenset(
        {"cancelled", "abandoned", "research_only", "superseded", "archived"}
    ),
    "failed_in_production": frozenset({"deployed", "archived", "superseded"}),
    "cancelled": frozenset({"pending", "archived", "superseded"}),
    "abandoned": frozenset({"pending", "archived", "superseded"}),
    "blocked": frozenset({"pending", "cancelled", "abandoned", "superseded", "archived"}),
    "superseded": frozenset({"archived"}),
    "archived": frozenset(),
}


class OutcomeStore(Protocol):
    """Persistence capabilities required by :class:`OutcomeService`."""

    def project_exists(self, project_id: str) -> bool: ...

    def get(self, model: type[object], identifier: str) -> object | None: ...

    def append_outcome_event(
        self, event: OutcomeEventRecord, outcome: OutcomeRecord
    ) -> OutcomeEventRecord: ...

    def outcome_events(self, project_id: str) -> list[OutcomeEventRecord]: ...


def allowed_transitions(status: str) -> frozenset[str]:
    """Return statuses reachable from *status*."""
    _validate_status(status)
    return _TRANSITIONS[status]


class OutcomeService:
    """Record outcome transitions while preserving their complete history."""

    def __init__(
        self,
        store: OutcomeStore,
        *,
        clock: Callable[[], datetime] | None = None,
        event_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._event_id_factory = event_id_factory or (lambda: f"outcome-event-{uuid4().hex}")

    def current(self, project_id: str) -> ProjectOutcome | None:
        """Return the current projection, or ``None`` before an outcome is recorded."""
        record = cast(OutcomeRecord | None, self._store.get(OutcomeRecord, project_id))
        if record is None:
            return None
        return _contract_from_record(record)

    def events(self, project_id: str) -> list[OutcomeEventContract]:
        """Return the immutable event history in persistence order."""
        return [_contract_from_event(event) for event in self._store.outcome_events(project_id)]

    def transition(
        self,
        project_id: str,
        new_status: str,
        *,
        reason: str,
        owner: str,
        evidence: Sequence[str] = (),
        notes: str | None = None,
        related_report_id: str | None = None,
        related_experiment_id: str | None = None,
        outcome: ProjectOutcome | None = None,
        decision_id: str | None = None,
        approval_id: str | None = None,
    ) -> OutcomeEventContract:
        """Validate and append one outcome event and its current-state projection."""
        _validate_status(new_status)
        if not reason.strip():
            raise ValueError("outcome reason must not be empty")
        if not self._store.project_exists(project_id):
            raise OutcomeNotFound(f"project does not exist: {project_id}")

        current = self.current(project_id)
        previous_status = current.current_status if current else "pending"
        if new_status not in allowed_transitions(previous_status):
            raise InvalidOutcomeTransition(
                f"cannot transition outcome from {previous_status!r} to {new_status!r}"
            )
        evidence_list = [item for item in evidence if item.strip()]
        if new_status in {"deployed", "successful_in_production"}:
            _require_deployment_authorization(
                self._store,
                project_id,
                decision_id=decision_id,
                approval_id=approval_id,
            )
            evidence_list.extend([f"decision:{decision_id}", f"approval:{approval_id}"])
        if new_status == "successful_in_production" and not evidence_list:
            raise MissingProductionEvidence(
                "successful_in_production requires at least one evidence reference"
            )
        if new_status == "successful_in_production" and len(evidence_list) == 2:
            raise MissingProductionEvidence(
                "successful_in_production requires production evidence in addition to authorization"
            )

        now = _ensure_utc(self._clock())
        if current is not None and now <= current.last_updated_at:
            now = current.last_updated_at + timedelta(microseconds=1)
        next_outcome = _next_outcome(
            project_id,
            current,
            new_status=new_status,
            owner=owner,
            now=now,
            supplied=outcome,
        )
        event = OutcomeEventRecord(
            event_id=self._event_id_factory(),
            project_id=project_id,
            previous_status=None if current is None else previous_status,
            new_status=new_status,
            reason=reason,
            evidence=evidence_list,
            owner=owner,
            created_at=now,
            related_report_id=related_report_id,
            related_experiment_id=related_experiment_id,
            notes=notes,
        )
        self._store.append_outcome_event(event, OutcomeRecord(**_record_values(next_outcome)))
        return _contract_from_event(event)


def _next_outcome(
    project_id: str,
    current: ProjectOutcome | None,
    *,
    new_status: str,
    owner: str,
    now: datetime,
    supplied: ProjectOutcome | None,
) -> ProjectOutcome:
    if supplied is not None:
        if supplied.project_id != project_id:
            raise ValueError("supplied outcome project_id does not match project_id")
        return supplied.model_copy(
            update={"current_status": new_status, "owner": owner, "last_updated_at": now}
        )
    if current is not None:
        return current.model_copy(
            update={"current_status": new_status, "owner": owner, "last_updated_at": now}
        )
    return ProjectOutcome(
        project_id=project_id, current_status=new_status, owner=owner, last_updated_at=now
    )


def _record_values(outcome: ProjectOutcome) -> dict[str, object]:
    values = outcome.model_dump(mode="json")
    return {
        "project_id": outcome.project_id,
        "current_status": outcome.current_status,
        "owner": outcome.owner,
        "decision_date": outcome.decision_date,
        "last_updated_at": outcome.last_updated_at,
        "payload": values,
    }


def _contract_from_record(record: OutcomeRecord) -> ProjectOutcome:
    values = dict(record.payload)
    values.update(
        project_id=record.project_id,
        current_status=record.current_status,
        owner=record.owner,
        decision_date=record.decision_date,
        last_updated_at=record.last_updated_at,
    )
    return ProjectOutcome.model_validate(values)


def _contract_from_event(event: OutcomeEventRecord) -> OutcomeEventContract:
    return OutcomeEventContract(
        event_id=event.event_id,
        project_id=event.project_id,
        previous_status=event.previous_status,
        new_status=event.new_status,
        reason=event.reason,
        evidence=event.evidence,
        owner=event.owner,
        created_at=event.created_at,
        related_report_id=event.related_report_id,
        related_experiment_id=event.related_experiment_id,
        notes=event.notes,
    )


def _validate_status(status: str) -> None:
    if status not in OUTCOME_STATUSES:
        raise UnknownOutcomeStatus(f"unsupported outcome status: {status}")


def _require_deployment_authorization(
    store: OutcomeStore,
    project_id: str,
    *,
    decision_id: str | None,
    approval_id: str | None,
) -> None:
    if not decision_id or not approval_id:
        raise MissingDeploymentApproval(
            "deployment-related outcomes require decision_id and approval_id"
        )
    decision = cast(Decision | None, store.get(Decision, decision_id))
    approval = cast(Approval | None, store.get(Approval, approval_id))
    if (
        decision is None
        or decision.project_id != project_id
        or not decision.allowed
        or _decision_action(decision) not in {"deployment", "deploy_model"}
        or approval is None
        or approval.project_id != project_id
        or approval.approval_status != "approved"
        or approval.decision_id != decision_id
        or approval.action_type != _decision_action(decision)
    ):
        raise MissingDeploymentApproval(
            "deployment-related outcome authorization is missing, invalid, or unlinked"
        )


def _decision_action(decision: Decision) -> str | None:
    """Read the action from the persisted DecisionRecord payload."""
    action = decision.payload.get("action_requested")
    return action if isinstance(action, str) else None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
