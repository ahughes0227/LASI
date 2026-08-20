"""Behaviour that differs between the two supported backends.

SQLite serialises writes, so it silently satisfies assumptions PostgreSQL does not.
Anything relying on concurrent row access is therefore only meaningfully tested against
PostgreSQL, and is skipped rather than faked when no server is configured.
"""

import os

import pytest
from services.memory import Base, create_engine, create_session_factory
from services.memory.models import (
    Project,
    ReasoningRubricRecord,
    ResearchAssignmentRecord,
    RuntimeTaskRecord,
    TaskGraphProposalRecord,
)
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql, sqlite

POSTGRES_URL = os.environ.get("LASI_TEST_DATABASE_URL", "")
requires_postgres = pytest.mark.skipif(
    not POSTGRES_URL.startswith("postgresql"),
    reason="set LASI_TEST_DATABASE_URL to a PostgreSQL server to run this",
)


def _lease_query():
    return (
        select(RuntimeTaskRecord)
        .where(RuntimeTaskRecord.status == "ready")
        .order_by(RuntimeTaskRecord.priority.desc(), RuntimeTaskRecord.sequence)
        .with_for_update(skip_locked=True)
    )


def test_lease_query_locks_rows_on_postgresql() -> None:
    """The clause has to reach the database, not merely be written in the source."""
    compiled = str(_lease_query().compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_lease_query_is_still_valid_on_sqlite() -> None:
    """SQLite has no row locking; the clause is dropped rather than rejected."""
    compiled = str(_lease_query().compile(dialect=sqlite.dialect()))

    assert "FOR UPDATE" not in compiled


@pytest.fixture
def postgres_engine():
    engine = create_engine(POSTGRES_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed_two_ready_tasks(engine) -> None:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(
            Project(
                project_id="p", project_name="P", problem_type="classification", modality="tabular"
            )
        )
        session.add(
            ResearchAssignmentRecord(
                assignment_id="a", project_id="p", objective="o", status="running"
            )
        )
        session.add(
            ReasoningRubricRecord(
                rubric_key="none", rubric_id="none", version="1.0", capability="research"
            )
        )
        session.add(
            TaskGraphProposalRecord(
                proposal_id="prop",
                assignment_id="a",
                project_id="p",
                observed_revision=1,
                status="accepted",
            )
        )
        session.flush()
        for index in (1, 2):
            session.add(
                RuntimeTaskRecord(
                    task_id=f"task-{index}",
                    assignment_id="a",
                    project_id="p",
                    proposal_id="prop",
                    task_type="orchestration",
                    agent_role="coordinator",
                    status="ready",
                    sequence=index,
                    rubric_key="none",
                )
            )
        session.commit()


@requires_postgres
@pytest.mark.postgres
def test_two_workers_cannot_lease_the_same_ready_task(postgres_engine) -> None:
    """The race the fix exists for, held open deterministically rather than threaded."""
    _seed_two_ready_tasks(postgres_engine)
    session_factory = create_session_factory(postgres_engine)

    first_session = session_factory()
    second_session = session_factory()
    try:
        first = first_session.scalar(_lease_query())
        assert first is not None
        # First worker's transaction stays open, holding the row lock.
        second = second_session.scalar(_lease_query())

        assert second is not None, "second worker should skip the locked row, not starve"
        assert second.task_id != first.task_id
    finally:
        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()


@requires_postgres
@pytest.mark.postgres
def test_the_last_ready_task_is_skipped_rather_than_blocking(postgres_engine) -> None:
    """With one row available, the second worker gets nothing instead of waiting."""
    _seed_two_ready_tasks(postgres_engine)
    session_factory = create_session_factory(postgres_engine)
    with session_factory() as only_session:
        only_session.execute(
            text("UPDATE runtime_tasks SET status = 'completed' WHERE task_id = 'task-2'")
        )
        only_session.commit()

    first_session = session_factory()
    second_session = session_factory()
    try:
        assert first_session.scalar(_lease_query()) is not None

        # SKIP LOCKED is what makes this return rather than block until timeout.
        assert second_session.scalar(_lease_query()) is None
    finally:
        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()


@requires_postgres
@pytest.mark.postgres
def test_foreign_keys_are_enforced_without_a_pragma(postgres_engine) -> None:
    """SQLite needs `PRAGMA foreign_keys=ON`; PostgreSQL must not need the equivalent."""
    from sqlalchemy.exc import IntegrityError

    session_factory = create_session_factory(postgres_engine)
    with session_factory() as session:
        session.add(
            ResearchAssignmentRecord(
                assignment_id="orphan",
                project_id="no-such-project",
                objective="o",
                status="running",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@requires_postgres
@pytest.mark.postgres
def test_pgvector_is_available_on_the_configured_server(postgres_engine) -> None:
    """ADR-003 keeps similarity search in the same database; this proves it can be.

    No column uses pgvector yet: there is no embedding producer until the reasoning
    layer exists, and a vector column with nothing to write into it would be
    speculative. This asserts only that adopting it needs no second datastore.
    """
    with postgres_engine.connect() as connection:
        available = connection.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        ).scalar()

    assert available == 1
