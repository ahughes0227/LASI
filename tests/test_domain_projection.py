from datetime import UTC, datetime
from pathlib import Path

from services.context.models import (
    EvidenceClaim,
    EvidenceStatus,
    ExperimentContext,
    ProjectState,
)
from services.domain.models import DomainStateSnapshot
from services.domain.projection import DomainStateProjector


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def project(state: ProjectState) -> DomainStateSnapshot:
    return DomainStateProjector().project_project_state(state, revision=3, created_at=NOW)


def test_projector_maps_project_experiment_and_claim_state() -> None:
    snapshot = project(
        ProjectState(
            project_id="p1",
            objective="Improve recall",
            constraints="Local only",
            experiments=[ExperimentContext(project_id="p1", experiment_id="e1", hypothesis="h")],
            claims=[
                EvidenceClaim(
                    claim_id="c1",
                    project_id="p1",
                    claim="The split is valid",
                    confidence="high",
                    status=EvidenceStatus.SUPPORTED,
                )
            ],
            recommendation="Run evaluation",
        )
    )
    by_key = {(fact.subject, fact.predicate): fact for fact in snapshot.facts}
    assert by_key[("project", "objective")].value == "Improve recall"
    assert by_key[("project", "constraints")].authority == 100
    assert by_key[("experiment:e1", "status")].value == "planned"
    assert by_key[("experiment:e1", "hypothesis")].value == "h"
    assert by_key[("claim:c1", "statement")].status == "observed"
    assert by_key[("project", "recommendation")].confidence == 0.5


def test_projector_maps_conflicting_and_invalidated_claims() -> None:
    snapshot = project(
        ProjectState(
            project_id="p1",
            claims=[
                EvidenceClaim(claim_id="c1", project_id="p1", claim="x", confidence="medium", status="conflicting"),
                EvidenceClaim(claim_id="c2", project_id="p1", claim="y", confidence="high", status="invalidated"),
            ],
        )
    )
    facts = {fact.subject: fact for fact in snapshot.facts if fact.predicate == "statement"}
    assert facts["claim:c1"].status == "conflicting"
    assert facts["claim:c2"].status == "invalidated"


def test_projector_maps_known_confidence_labels() -> None:
    claims = [
        EvidenceClaim(claim_id=label, project_id="p1", claim=label, confidence=label, status="weak")
        for label in ("low", "medium", "high")
    ]
    snapshot = project(ProjectState(project_id="p1", claims=claims))
    assert {fact.subject: fact.confidence for fact in snapshot.facts if fact.predicate == "statement"} == {
        "claim:low": 0.25,
        "claim:medium": 0.5,
        "claim:high": 0.8,
    }


def test_projector_maps_unknown_confidence_to_zero() -> None:
    snapshot = project(
        ProjectState(
            project_id="p1",
            claims=[EvidenceClaim(claim_id="c1", project_id="p1", claim="x", confidence="certain", status="weak")],
        )
    )
    assert all(fact.confidence == 0 for fact in snapshot.facts if fact.subject == "claim:c1")


def test_projector_emits_one_fact_per_claim_dependency() -> None:
    snapshot = project(
        ProjectState(
            project_id="p1",
            claims=[
                EvidenceClaim(
                    claim_id="c1",
                    project_id="p1",
                    claim="x",
                    confidence="high",
                    status="supported",
                    depends_on_claim_ids=["c3", "c2", "c3"],
                )
            ],
        )
    )
    dependencies = [fact for fact in snapshot.facts if fact.predicate == "depends_on"]
    assert [fact.value for fact in dependencies] == ["c2", "c3"]
    assert len({fact.fact_id for fact in dependencies}) == 2


def test_projector_output_is_deterministic_under_input_reordering() -> None:
    one = ProjectState(
        project_id="p1",
        experiments=[ExperimentContext(project_id="p1", experiment_id="b", hypothesis="b"), ExperimentContext(project_id="p1", experiment_id="a", hypothesis="a")],
        claims=[EvidenceClaim(claim_id="b", project_id="p1", claim="b", confidence="low", status="weak"), EvidenceClaim(claim_id="a", project_id="p1", claim="a", confidence="low", status="weak")],
    )
    two = one.model_copy(update={"experiments": list(reversed(one.experiments)), "claims": list(reversed(one.claims))})
    assert project(one).model_dump() == project(two).model_dump()
    assert [fact.fact_id for fact in project(one).facts] == sorted(fact.fact_id for fact in project(one).facts)


def test_projector_does_not_read_or_write_icm(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("projector accessed ICM filesystem")

    monkeypatch.setattr(Path, "read_text", fail)
    monkeypatch.setattr(Path, "write_text", fail)
    project(ProjectState(project_id="p1", objective="x"))
