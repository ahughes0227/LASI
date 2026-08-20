"""Replay recorded decisions against several ranker variants.

This is the consumer Hydra was adopted for: composing ranker, retrieval, and threshold
settings into a matrix, running them over the same decisions, and recording each result
so the variants can be compared rather than argued about.

It replays *admissible sets that were actually produced*, so a variant is measured
against real decisions rather than synthetic ones.  It changes nothing: no plan is
executed, and no ranker is promoted by running well here.
"""

from __future__ import annotations

from services.planner import LexicographicPlanRanker, PlanCandidate
from services.planner.domain_models import DomainGoal

from .models import RankerVariant, SweepResult, VariantOutcome


class RankerSweep:
    """Runs each variant over the same replayed decisions."""

    def __init__(self, decisions: list[tuple[DomainGoal, list[PlanCandidate]]]) -> None:
        self.decisions = decisions
        self.default = LexicographicPlanRanker()

    def run(self, variants: dict[str, object], specs: list[RankerVariant]) -> SweepResult:
        by_name = {spec.name: spec for spec in specs}
        outcomes: list[VariantOutcome] = []
        for name, ranker in variants.items():
            outcomes.append(self._evaluate(name, ranker, by_name.get(name)))
        return SweepResult(variants=outcomes)

    def _evaluate(self, name: str, ranker: object, spec: RankerVariant | None) -> VariantOutcome:
        real_choices = 0
        differed = 0
        for goal, candidates in self.decisions:
            if len(candidates) > 1:
                real_choices += 1
            chosen = ranker.rank(candidates, goal=goal)[0]  # type: ignore[attr-defined]
            baseline = self.default.rank(candidates, goal=goal)[0]
            if len(candidates) > 1 and chosen.candidate_id != baseline.candidate_id:
                differed += 1
        return VariantOutcome(
            name=name,
            ranker_id=getattr(ranker, "ranker_id", "unknown"),
            ranker_version=getattr(ranker, "ranker_version", "unknown"),
            decisions=len(self.decisions),
            real_choices=real_choices,
            differed_from_default=differed,
        )
