import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from services.domain.models import (
    DomainFact,
    DomainPredicate,
    DomainStateSnapshot,
    PredicateOperator,
)
from services.domain.mutation_models import MutationAuthorization, MutationPreview
from services.domain.mutations import GovernedMutationRunner

NOW = datetime.now(UTC)


def _fact(value=True, fact_id="mutation-fact"):
    return DomainFact(
        fact_id=fact_id,
        project_id="project",
        subject="derived",
        predicate="ready",
        value=value,
        status="observed",
        confidence=1,
        authority=10,
        evidence_refs=["mutation-output"],
        source="fake-handler",
        observed_at=NOW,
    )


def _snapshot():
    return DomainStateSnapshot(project_id="project", revision=1, facts=[], created_at=NOW)


def _predicate(value=True):
    return DomainPredicate(
        subject="derived", predicate="ready", operator=PredicateOperator.EQUALS, value=value
    )


def _preview(source: Path, *, preconditions=None, postconditions=None, compensate=None):
    return MutationPreview(
        mutation_id="mutation-1",
        project_id="project",
        action="edit-derived",
        source_ref=str(source),
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        derived_ref="derived://artifact-1",
        changes=["write derived artifact"],
        required_preconditions=preconditions or [],
        expected_postconditions=postconditions or [],
        compensation_action=compensate,
        created_at=NOW,
    )


class FakeLookup:
    def __init__(self, authorization):
        self.authorization = authorization
        self.calls = 0

    def authorization_for(self, preview):
        self.calls += 1
        return self.authorization


class FakeHandler:
    def __init__(self, outside=None, *, facts=None, error=None):
        self.outside = outside
        self.facts = facts or []
        self.error = error
        self.apply_calls = 0
        self.compensate_calls = 0

    def apply(self, preview, workdir):
        self.apply_calls += 1
        if self.error:
            raise RuntimeError(self.error)
        output = self.outside or workdir / "output.txt"
        output.write_text("derived", encoding="utf-8")
        return output, self.facts

    def compensate(self, preview, output, workdir):
        self.compensate_calls += 1
        compensation = workdir / "compensation.txt"
        compensation.write_text("compensated", encoding="utf-8")
        return compensation


def _allowed(mutation_id="mutation-1"):
    return MutationAuthorization(
        mutation_id=mutation_id,
        decision_id="decision-1",
        approval_id=None,
        allowed=True,
        conditions=[],
    )


def test_precondition_failure_blocks_before_authorization(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    lookup = FakeLookup(_allowed())
    handler = FakeHandler()

    result = GovernedMutationRunner().run(
        _preview(source, preconditions=[_predicate()]),
        handler,
        lookup,
        _snapshot(),
        tmp_path / "work",
    )

    assert result.status == "blocked"
    assert lookup.calls == 0
    assert handler.apply_calls == 0


def test_denied_authorization_blocks_before_apply(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    denied = MutationAuthorization(
        mutation_id="mutation-1",
        decision_id="decision-1",
        approval_id=None,
        allowed=False,
        conditions=[],
    )
    handler = FakeHandler()

    result = GovernedMutationRunner().run(
        _preview(source), handler, FakeLookup(denied), _snapshot(), tmp_path / "work"
    )

    assert result.status == "blocked"
    assert handler.apply_calls == 0


def test_authorization_must_match_mutation(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    handler = FakeHandler()

    result = GovernedMutationRunner().run(
        _preview(source), handler, FakeLookup(_allowed("other")), _snapshot(), tmp_path / "work"
    )

    assert result.status == "blocked"
    assert handler.apply_calls == 0


def test_output_must_remain_inside_workdir(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    handler = FakeHandler(outside=tmp_path / "outside.txt")

    result = GovernedMutationRunner().run(
        _preview(source), handler, FakeLookup(_allowed()), _snapshot(), tmp_path / "work"
    )

    assert result.status == "failed"
    assert "inside workdir" in result.errors[0]


def test_successful_mutation_validates_postconditions(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    handler = FakeHandler(facts=[_fact()])

    result = GovernedMutationRunner().run(
        _preview(source, postconditions=[_predicate()]),
        handler,
        FakeLookup(_allowed()),
        _snapshot(),
        tmp_path / "work",
    )

    assert result.status == "applied"
    assert result.output_hash
    assert result.validation_results[0].satisfied


def test_failed_postcondition_runs_compensation_once(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    handler = FakeHandler()

    result = GovernedMutationRunner().run(
        _preview(source, postconditions=[_predicate()], compensate="restore"),
        handler,
        FakeLookup(_allowed()),
        _snapshot(),
        tmp_path / "work",
    )

    assert result.status == "compensated"
    assert handler.compensate_calls == 1
    assert result.compensation_ref


def test_failed_postcondition_without_compensation_is_quarantined(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    handler = FakeHandler()

    result = GovernedMutationRunner().run(
        _preview(source, postconditions=[_predicate()]),
        handler,
        FakeLookup(_allowed()),
        _snapshot(),
        tmp_path / "work",
    )

    assert result.status == "quarantined"
    assert handler.compensate_calls == 0


def test_source_file_is_not_modified(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    before = source.read_bytes()

    result = GovernedMutationRunner().run(
        _preview(source), FakeHandler(), FakeLookup(_allowed()), _snapshot(), tmp_path / "work"
    )

    assert result.status == "applied"
    assert source.read_bytes() == before


def test_handler_exception_is_recorded_as_failure(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")

    result = GovernedMutationRunner().run(
        _preview(source),
        FakeHandler(error="boom"),
        FakeLookup(_allowed()),
        _snapshot(),
        tmp_path / "work",
    )

    assert result.status == "failed"
    assert result.errors == ["boom"]


def test_workdir_must_be_new(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    workdir = tmp_path / "work"
    workdir.mkdir()

    with pytest.raises(FileExistsError):
        GovernedMutationRunner().run(
            _preview(source), FakeHandler(), FakeLookup(_allowed()), _snapshot(), workdir
        )
