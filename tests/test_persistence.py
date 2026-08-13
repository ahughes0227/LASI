"""Focused tests for operational-memory persistence invariants."""

from datetime import UTC, datetime

import pytest
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import Dataset, DatasetVersion, Outcome, OutcomeEvent, Project
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def memory() -> OperationalMemory:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return OperationalMemory(create_session_factory(engine))


def test_foreign_keys_are_enforced_and_timestamps_are_utc(memory: OperationalMemory) -> None:
    project = memory.add(
        Project(
            project_id="p1", project_name="P", problem_type="classification", modality="tabular"
        )
    )
    assert project.created_at.tzinfo == UTC
    assert memory.project_exists("p1")

    with pytest.raises(IntegrityError):
        memory.add(
            DatasetVersion(
                dataset_version_id="dv1", dataset_id="missing", version="v1", data_hash="hash"
            )
        )


def test_transaction_rolls_back_all_records(memory: OperationalMemory) -> None:
    with pytest.raises(RuntimeError):
        with memory.transaction() as session:
            session.add(Project(project_id="p2", project_name="P", problem_type="x", modality="y"))
            raise RuntimeError("abort")
    assert not memory.project_exists("p2")


def test_dataset_lineage_is_foreign_keyed(memory: OperationalMemory) -> None:
    memory.add(Project(project_id="p3", project_name="P", problem_type="x", modality="y"))
    memory.add(Dataset(dataset_id="d3", project_id="p3", name="D"))
    parent = memory.add(
        DatasetVersion(
            dataset_version_id="dv-parent",
            dataset_id="d3",
            project_id="p3",
            version="v1",
            data_hash="a",
        )
    )
    child = memory.add(
        DatasetVersion(
            dataset_version_id="dv-child",
            dataset_id="d3",
            project_id="p3",
            parent_version_id=parent.dataset_version_id,
            version="v2",
            data_hash="b",
        )
    )
    assert child.parent_version_id == "dv-parent"


def test_outcome_events_are_append_only_and_update_current_projection(
    memory: OperationalMemory,
) -> None:
    memory.add(Project(project_id="p4", project_name="P", problem_type="x", modality="y"))
    first = OutcomeEvent(
        event_id="e1", project_id="p4", new_status="deployed", reason="released", owner="owner"
    )
    memory.append_outcome_event(
        first,
        Outcome(
            project_id="p4",
            current_status="deployed",
            owner="owner",
            last_updated_at=datetime.now(UTC),
        ),
    )
    second = OutcomeEvent(
        event_id="e2",
        project_id="p4",
        new_status="failed_in_production",
        reason="drift",
        owner="owner",
    )
    memory.append_outcome_event(
        second,
        Outcome(
            project_id="p4",
            current_status="failed_in_production",
            owner="owner",
            last_updated_at=datetime.now(UTC),
        ),
    )
    assert [event.new_status for event in memory.outcome_events("p4")] == [
        "deployed",
        "failed_in_production",
    ]
    assert memory.get(Outcome, "p4").current_status == "failed_in_production"


def test_database_has_foreign_key_pragma(memory: OperationalMemory) -> None:
    session_factory = memory._session_factory
    with session_factory() as session:
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
