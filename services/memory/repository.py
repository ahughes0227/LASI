"""Small transactional repository for operational memory records."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Outcome, OutcomeEvent, Project

ModelT = TypeVar("ModelT")


class OperationalMemory:
    """Persistence boundary; authorization remains outside this class."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit on success and roll back the complete transaction on failure."""
        with self._session_factory() as session:
            try:
                with session.begin():
                    yield session
            except Exception:
                session.rollback()
                raise

    @contextmanager
    def read_session(self) -> Iterator[Session]:
        """Expose a short-lived read-only session to projection/query services."""
        with self._session_factory() as session:
            yield session

    def add(self, record: ModelT) -> ModelT:
        with self.transaction() as session:
            session.add(record)
            session.flush()
        return record

    def add_contract(self, record: ModelT, contract: BaseModel) -> ModelT:
        """Attach a contract's JSON representation to an already mapped record."""
        if hasattr(record, "payload"):
            record.payload = contract.model_dump(mode="json")
        return self.add(record)

    def get(self, model: type[ModelT], identifier: Any) -> ModelT | None:
        with self._session_factory() as session:
            return cast(ModelT | None, session.get(model, identifier))

    def list_for_project(self, model: type[ModelT], project_id: str) -> list[ModelT]:
        with self._session_factory() as session:
            column = cast(Any, model).project_id
            return list(session.scalars(select(model).where(column == project_id)))

    def list_all(self, model: type[ModelT]) -> list[ModelT]:
        """Return all records of a type for cross-project operational analysis."""
        with self._session_factory() as session:
            return list(session.scalars(select(model)))

    def append_outcome_event(self, event: OutcomeEvent, outcome: Outcome) -> OutcomeEvent:
        """Append an event and update the current projection atomically."""
        with self.transaction() as session:
            current = session.get(Outcome, outcome.project_id)
            event.previous_status = current.current_status if current is not None else None
            if current is None:
                session.add(outcome)
            else:
                current.current_status = outcome.current_status
                current.owner = outcome.owner
                current.decision_date = outcome.decision_date
                current.last_updated_at = outcome.last_updated_at
                current.payload = outcome.payload
            session.add(event)
            session.flush()
        return event

    def outcome_events(self, project_id: str) -> list[OutcomeEvent]:
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(OutcomeEvent)
                    .where(OutcomeEvent.project_id == project_id)
                    .order_by(OutcomeEvent.created_at, OutcomeEvent.event_id)
                )
            )

    def project_exists(self, project_id: str) -> bool:
        with self._session_factory() as session:
            return session.get(Project, project_id) is not None


def ensure_utc(value: datetime) -> datetime:
    """Normalize caller timestamps before persistence."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
