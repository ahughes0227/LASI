from datetime import UTC, datetime

import pytest
from services.domain.confidence import (
    ConfidenceAggregator,
    EvidenceSignal,
    fact_from_assessment,
)

NOW = datetime.now(UTC)


def signal(ref, *, confidence=1, authority=100, supports=True, source="source"):
    return EvidenceSignal(
        evidence_ref=ref,
        confidence=confidence,
        authority=authority,
        supports=supports,
        independent_source=source,
    )


def test_empty_signals_are_unsupported():
    assessment = ConfidenceAggregator().assess([])
    assert assessment.confidence == 0
    assert assessment.status == "unsupported"
    assert assessment.supporting_refs == []
    assert assessment.counter_refs == []


def test_duplicate_identical_signal_is_counted_once():
    assessment = ConfidenceAggregator().assess([signal("e"), signal("e")])
    assert assessment.confidence == 1
    assert assessment.supporting_refs == ["e"]
    assert assessment.independent_source_count == 1


def test_duplicate_conflicting_signal_is_rejected():
    with pytest.raises(ValueError, match="conflicting signal values"):
        ConfidenceAggregator().assess([signal("e"), signal("e", authority=99)])


def test_same_source_is_not_double_counted():
    assessment = ConfidenceAggregator().assess(
        [
            signal("low", confidence=0.5, source="same"),
            signal("high", confidence=0.8, source="same"),
        ]
    )
    assert assessment.confidence == 0.8
    assert assessment.supporting_refs == ["high"]


def test_independent_support_increases_confidence():
    one = ConfidenceAggregator().assess([signal("one", confidence=0.6)])
    two = ConfidenceAggregator().assess(
        [signal("one", confidence=0.6), signal("two", confidence=0.6, source="other")]
    )
    assert two.confidence > one.confidence
    assert two.status == "strongly_supported"


def test_strong_support_and_counterevidence_are_conflicting():
    assessment = ConfidenceAggregator().assess(
        [signal("support"), signal("counter", supports=False, source="other")]
    )
    assert assessment.status == "conflicting"
    assert assessment.confidence == 1
    assert assessment.counter_refs == ["counter"]


@pytest.mark.parametrize(
    ("weight", "status"),
    [
        (0.199999, "unsupported"),
        (0.2, "weak"),
        (0.5, "supported"),
        (0.8, "strongly_supported"),
    ],
)
def test_status_thresholds_are_exact(weight, status):
    assessment = ConfidenceAggregator().assess([signal("e", confidence=weight)])
    assert assessment.status == status


def test_fact_from_assessment_maps_status_and_evidence():
    assessment = ConfidenceAggregator().assess(
        [
            signal("z", confidence=0.8),
            signal("a", confidence=0.6, supports=False, source="other"),
        ]
    )
    fact = fact_from_assessment(
        fact_id="fact-1",
        project_id="project-1",
        subject="model",
        predicate="ready",
        value=True,
        assessment=assessment,
        source="aggregator",
        observed_at=NOW,
    )
    assert fact.status == "conflicting"
    assert fact.confidence == assessment.confidence
    assert fact.authority == assessment.maximum_authority
    assert fact.evidence_refs == ["a", "z"]


def test_aggregation_is_order_independent():
    signals = [
        signal("z", confidence=0.6, source="z-source"),
        signal("a", confidence=0.4, source="a-source"),
        signal("counter", confidence=0.3, supports=False, source="counter-source"),
    ]
    aggregator = ConfidenceAggregator()
    assert aggregator.assess(signals) == aggregator.assess(list(reversed(signals)))
