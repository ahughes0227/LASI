from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from services.domain.models import (
    DomainFact,
    DomainPredicate,
    DomainStateSnapshot,
    PredicateOperator,
)
from services.domain.predicates import PredicateEvaluator

NOW = datetime.now(UTC)


def fact(fact_id="fact", *, value=True, status="observed", confidence=1, authority=10, **kwargs):
    fields = dict(
        fact_id=fact_id,
        project_id="project",
        subject="model",
        predicate="ready",
        value=value,
        status=status,
        confidence=confidence,
        authority=authority,
        evidence_refs=["evidence"],
        source="test",
        observed_at=NOW,
    )
    fields.update(kwargs)
    return DomainFact(**fields)


def snapshot(*facts):
    return DomainStateSnapshot(project_id="project", revision=1, facts=list(facts), created_at=NOW)


def test_verified_fact_requires_evidence_and_minimum_confidence():
    with pytest.raises(ValidationError):
        fact(status="verified", confidence=0.79)
    with pytest.raises(ValidationError):
        fact(status="verified", evidence_refs=[])


def test_snapshot_rejects_cross_project_fact():
    other = fact()
    other.project_id = "other"
    with pytest.raises(ValidationError):
        snapshot(other)


def test_snapshot_rejects_duplicate_fact_ids():
    with pytest.raises(ValidationError):
        snapshot(fact("same"), fact("same", value=False))


def test_active_facts_exclude_invalidated_conflicting_and_expired():
    state = snapshot(
        fact("active"),
        fact("invalid", status="invalidated"),
        fact("conflicting", status="conflicting"),
        fact("expired", expires_at=NOW - timedelta(seconds=1)),
    )
    assert [item.fact_id for item in state.active_facts("model", "ready")] == ["active"]


def test_equals_respects_confidence_and_authority():
    result = PredicateEvaluator().evaluate(
        DomainPredicate(
            subject="model",
            predicate="ready",
            operator=PredicateOperator.EQUALS,
            value=True,
            minimum_confidence=0.8,
            minimum_authority=50,
        ),
        snapshot(
            fact("good", authority=50), fact("weak", confidence=0.5), fact("low_auth", authority=1)
        ),
    )
    assert result.satisfied
    assert result.matching_fact_ids == ["good"]
    assert result.rejected_fact_ids == ["low_auth", "weak"]


def test_exists_and_not_exists_use_active_facts():
    evaluator = PredicateEvaluator()
    state = snapshot(fact("invalid", status="invalidated"))
    exists = evaluator.evaluate(
        DomainPredicate(subject="model", predicate="ready", operator="exists"), state
    )
    missing = evaluator.evaluate(
        DomainPredicate(subject="model", predicate="ready", operator="not_exists"), state
    )
    assert not exists.satisfied
    assert missing.satisfied


def test_numeric_operators_do_not_coerce_strings():
    result = PredicateEvaluator().evaluate(
        DomainPredicate(
            subject="model", predicate="ready", operator="greater_than_or_equal", value=10
        ),
        snapshot(fact(value="10")),
    )
    assert not result.satisfied
    assert result.rejected_fact_ids == ["fact"]


def test_in_set_requires_fact_value_membership():
    evaluator = PredicateEvaluator()
    result = evaluator.evaluate(
        DomainPredicate(subject="model", predicate="ready", operator="in_set", value=["a", "b"]),
        snapshot(fact(value="b")),
    )
    assert result.satisfied
    assert result.matching_fact_ids == ["fact"]
    with pytest.raises(ValidationError):
        DomainPredicate(subject="model", predicate="ready", operator="in_set", value=[])


def test_evaluate_all_preserves_input_order():
    predicates = [
        DomainPredicate(subject="model", predicate="ready", operator="exists"),
        DomainPredicate(subject="model", predicate="ready", operator="equals", value=True),
    ]
    results = PredicateEvaluator().evaluate_all(predicates, snapshot(fact()))
    assert [result.predicate.operator for result in results] == [
        PredicateOperator.EXISTS,
        PredicateOperator.EQUALS,
    ]
