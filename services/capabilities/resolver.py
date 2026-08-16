"""Deterministic structural deduplication for capability requests."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from services.contracts import (
    CapabilityCandidate,
    CapabilityResolution,
    CapabilitySpec,
    Provenance,
)

from .registry import CapabilityRegistry

_TOKENS = re.compile(r"[a-z0-9]+")


class CapabilityResolver:
    """Resolve requests to REUSE, COMPOSE, EXTEND, or NEW before research begins."""

    def __init__(self, registry: CapabilityRegistry, *, extend_threshold: float = 0.55) -> None:
        self.registry = registry
        self.extend_threshold = extend_threshold

    def resolve(self, requested: CapabilitySpec) -> CapabilityResolution:
        compared = [self._compare(requested, existing) for existing in self.registry.all()]
        candidates = sorted(compared, key=lambda item: item.overall_score, reverse=True)

        exact = next(
            (
                item
                for item in candidates
                if item.input_coverage == 1
                and item.output_coverage == 1
                and item.operation_coverage == 1
                and item.guarantee_coverage == 1
                and item.constraint_coverage == 1
                and item.side_effect_compatibility == 1
                and not item.conflicting_exclusions
            ),
            None,
        )
        if exact is not None:
            return self._result(
                requested,
                "reuse",
                candidates,
                [exact.capability_id],
                [],
                "An existing capability satisfies the requested structural contract.",
            )

        compatible = [
            item
            for item in candidates
            if item.input_coverage == 1
            and item.output_coverage == 1
            and not item.conflicting_exclusions
            and item.operation_coverage > 0
        ]
        covered: set[str] = set()
        covered_guarantees: set[str] = set()
        selected: list[str] = []
        for item in compatible:
            existing = self.registry.get(item.capability_id, item.version)
            contribution = set(existing.operations) - covered
            if contribution:
                selected.append(item.capability_id)
                covered.update(existing.operations)
                covered_guarantees.update(existing.guarantees)
            if set(requested.operations).issubset(covered) and set(requested.guarantees).issubset(
                covered_guarantees
            ):
                break
        if (
            len(selected) > 1
            and set(requested.operations).issubset(covered)
            and set(requested.guarantees).issubset(covered_guarantees)
        ):
            return self._result(
                requested,
                "compose",
                candidates,
                selected,
                [],
                "Multiple existing capabilities cover the requested operations when composed.",
            )

        if compatible and compatible[0].overall_score >= self.extend_threshold:
            best = compatible[0]
            return self._result(
                requested,
                "extend",
                candidates,
                [best.capability_id],
                best.missing_requirements,
                "The closest capability owns the same responsibility but lacks requirements.",
            )

        missing = [
            *[f"operation:{item}" for item in requested.operations],
            *[f"guarantee:{item}" for item in requested.guarantees],
        ]
        return self._result(
            requested,
            "new",
            candidates,
            [],
            missing,
            "No existing capability or composition satisfies enough of the requested contract.",
        )

    @staticmethod
    def _compare(requested: CapabilitySpec, existing: CapabilitySpec) -> CapabilityCandidate:
        purpose = _jaccard(_words(requested.purpose), _words(existing.purpose))
        inputs = _coverage(requested.accepts, existing.accepts)
        outputs = _coverage(requested.produces, existing.produces)
        operations = _coverage(requested.operations, existing.operations)
        guarantees = _coverage(requested.guarantees, existing.guarantees)
        constraints = _coverage(requested.constraints, existing.constraints)
        undeclared_side_effects = sorted(set(existing.side_effects) - set(requested.side_effects))
        side_effects = 1.0 if not undeclared_side_effects else 0.0
        conflicts = sorted(set(requested.operations) & set(existing.does_not))
        score = (
            purpose * 0.10
            + inputs * 0.15
            + outputs * 0.15
            + operations * 0.30
            + guarantees * 0.10
            + constraints * 0.10
            + side_effects * 0.10
        )
        if conflicts:
            score *= 0.5
        missing = [
            *[
                f"operation:{item}"
                for item in requested.operations
                if item not in existing.operations
            ],
            *[
                f"guarantee:{item}"
                for item in requested.guarantees
                if item not in existing.guarantees
            ],
            *[
                f"constraint:{item}"
                for item in requested.constraints
                if item not in existing.constraints
            ],
            *[f"undeclared_side_effect:{item}" for item in undeclared_side_effects],
        ]
        return CapabilityCandidate(
            capability_id=existing.capability_id,
            version=existing.version,
            overall_score=round(score, 6),
            purpose_score=round(purpose, 6),
            input_coverage=inputs,
            output_coverage=outputs,
            operation_coverage=operations,
            guarantee_coverage=guarantees,
            constraint_coverage=constraints,
            side_effect_compatibility=side_effects,
            conflicting_exclusions=conflicts,
            missing_requirements=missing,
        )

    @staticmethod
    def _result(
        requested: CapabilitySpec,
        action: str,
        candidates: list[CapabilityCandidate],
        selected: list[str],
        missing: list[str],
        rationale: str,
    ) -> CapabilityResolution:
        return CapabilityResolution(
            resolution_id=f"capability-resolution-{uuid4().hex}",
            requested_capability_id=requested.capability_id,
            action=action,
            candidates=candidates,
            selected_capability_ids=selected,
            missing_requirements=missing,
            rationale=rationale,
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[requested.capability_id]),
        )


def _words(value: str) -> set[str]:
    return set(_TOKENS.findall(value.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _coverage(required: list[str], available: list[str]) -> float:
    if not required:
        return 1.0
    return len(set(required) & set(available)) / len(set(required))
