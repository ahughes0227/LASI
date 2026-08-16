"""Deterministic aggregation of independent evidence into domain facts."""

from datetime import datetime
from math import isclose, prod
from typing import Literal

from pydantic import Field

from services.contracts.models import StrictModel

from .models import DomainFact, DomainScalar


class EvidenceSignal(StrictModel):
    evidence_ref: str
    confidence: float = Field(ge=0, le=1)
    authority: int = Field(ge=0, le=100)
    supports: bool
    independent_source: str


class ConfidenceAssessment(StrictModel):
    confidence: float = Field(ge=0, le=1)
    status: Literal["unsupported", "weak", "supported", "strongly_supported", "conflicting"]
    supporting_refs: list[str]
    counter_refs: list[str]
    independent_source_count: int = Field(ge=0)
    maximum_authority: int = Field(ge=0, le=100)
    rationale: str


class ConfidenceAggregator:
    """Aggregate evidence without consulting provider prose or mutable state."""

    def assess(self, signals: list[EvidenceSignal]) -> ConfidenceAssessment:
        unique_signals: dict[str, EvidenceSignal] = {}
        for signal in signals:
            previous = unique_signals.get(signal.evidence_ref)
            if previous is not None:
                if previous != signal:
                    raise ValueError(
                        f"evidence_ref {signal.evidence_ref!r} has conflicting signal values"
                    )
                continue
            unique_signals[signal.evidence_ref] = signal

        selected: dict[tuple[str, bool], EvidenceSignal] = {}
        for signal in unique_signals.values():
            key = (signal.independent_source, signal.supports)
            current = selected.get(key)
            if current is None or self._selection_key(signal) > self._selection_key(current):
                selected[key] = signal

        retained = tuple(selected.values())
        supporting = tuple(signal for signal in retained if signal.supports)
        counter = tuple(signal for signal in retained if not signal.supports)
        support_score = self._combined_weight(supporting)
        counter_score = self._combined_weight(counter)

        status: Literal["unsupported", "weak", "supported", "strongly_supported", "conflicting"]
        if support_score >= 0.5 and counter_score >= 0.5:
            status = "conflicting"
            confidence = min(support_score, counter_score)
        else:
            net = support_score * (1 - counter_score)
            confidence = net
            if net < 0.2 and not isclose(net, 0.2, abs_tol=1e-12):
                status = "unsupported"
            elif net < 0.5 and not isclose(net, 0.5, abs_tol=1e-12):
                status = "weak"
            elif net < 0.8 and not isclose(net, 0.8, abs_tol=1e-12):
                status = "supported"
            else:
                status = "strongly_supported"

        supporting_refs = sorted(signal.evidence_ref for signal in supporting)
        counter_refs = sorted(signal.evidence_ref for signal in counter)
        maximum_authority = max((signal.authority for signal in retained), default=0)
        independent_source_count = len({signal.independent_source for signal in retained})

        return ConfidenceAssessment(
            confidence=round(confidence, 6),
            status=status,
            supporting_refs=supporting_refs,
            counter_refs=counter_refs,
            independent_source_count=independent_source_count,
            maximum_authority=maximum_authority,
            rationale=(
                f"support={support_score:.6f}; counter={counter_score:.6f}; "
                f"retained={len(retained)}"
            ),
        )

    @staticmethod
    def _selection_key(signal: EvidenceSignal) -> tuple[float, str]:
        weight = signal.confidence * (signal.authority / 100)
        # The reference tie-break makes equal-weight aggregation order-independent.
        return weight, signal.evidence_ref

    @staticmethod
    def _combined_weight(signals: tuple[EvidenceSignal, ...]) -> float:
        weights = [1 - signal.confidence * (signal.authority / 100) for signal in signals]
        return 1 - prod(weights)


def fact_from_assessment(
    *,
    fact_id: str,
    project_id: str,
    subject: str,
    predicate: str,
    value: DomainScalar,
    assessment: ConfidenceAssessment,
    source: str,
    observed_at: datetime,
) -> DomainFact:
    """Create a domain fact while preserving the assessment's evidence links."""

    status_map: dict[
        Literal["unsupported", "weak", "supported", "strongly_supported", "conflicting"],
        Literal["observed", "inferred", "verified", "conflicting"],
    ] = {
        "unsupported": "inferred",
        "weak": "inferred",
        "supported": "observed",
        "strongly_supported": "verified",
        "conflicting": "conflicting",
    }
    return DomainFact(
        fact_id=fact_id,
        project_id=project_id,
        subject=subject,
        predicate=predicate,
        value=value,
        status=status_map[assessment.status],
        confidence=assessment.confidence,
        authority=assessment.maximum_authority,
        evidence_refs=sorted(assessment.supporting_refs + assessment.counter_refs),
        source=source,
        observed_at=observed_at,
    )
