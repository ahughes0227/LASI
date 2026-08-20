"""Selection among admissible plans.

Admissibility is decided by search and policy in :mod:`services.planner.domain_planner`.
This module decides only *which* of the already-admissible plans is preferred, which is
the seam where learned selection replaces a hand-authored objective (ADR-002).

The invariant a ranker must not break: a ranker reorders the candidates it is given and
never introduces, removes, or alters one.  It therefore cannot widen the admissible set,
whatever it learns.  :func:`validate_ranking` enforces this at the call site.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from services.domain import DomainPolicyDecision

from .domain_models import ConsideredPlan, DomainGoal, PlannedCapabilityStep

#: Ordering of side-effect classes from least to most consequential.  Unknown classes
#: sort last so an unrecognised contract is never preferred by accident.
SIDE_EFFECT_RANK = {"none": 0, "read": 1, "create": 2, "update": 3, "delete": 4, "external": 5}
UNKNOWN_SIDE_EFFECT_RANK = 99


@dataclass(frozen=True)
class PlanCandidate:
    """One admissible plan, reduced to what selection is allowed to consider.

    Deliberately does not carry the simulated snapshot: a ranker that could read
    post-state would be able to re-derive admissibility, which is not its job.
    """

    candidate_id: str
    steps: tuple[PlannedCapabilityStep, ...]
    decisions: tuple[DomainPolicyDecision, ...]

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(step.capability_id for step in self.steps)

    @property
    def side_effect_score(self) -> int:
        return sum(
            SIDE_EFFECT_RANK.get(step.side_effect_class, UNKNOWN_SIDE_EFFECT_RANK)
            for step in self.steps
        )

    @property
    def approval_count(self) -> int:
        return sum(decision.outcome == "require_approval" for decision in self.decisions)

    def to_considered_plan(self, rank: int) -> ConsideredPlan:
        """Render this candidate as the durable record of a rejected alternative."""
        return ConsideredPlan(
            rank=rank,
            capability_ids=list(self.capability_ids),
            step_count=len(self.steps),
            side_effect_score=self.side_effect_score,
            approval_count=self.approval_count,
        )


@runtime_checkable
class PlanRanker(Protocol):
    """Orders admissible plans best-first.

    Implementations are identified by id and version so a recorded decision can be
    attributed to the policy that made it, and so two rankers can be compared.
    """

    ranker_id: str
    ranker_version: str

    def rank(
        self, candidates: Sequence[PlanCandidate], *, goal: DomainGoal
    ) -> tuple[PlanCandidate, ...]:
        """Return every candidate, best first.  Must be a permutation of the input."""
        ...


class RankingContractError(RuntimeError):
    """A ranker returned something other than a permutation of its candidates."""


def validate_ranking(
    ranked: Sequence[PlanCandidate], candidates: Sequence[PlanCandidate]
) -> tuple[PlanCandidate, ...]:
    """Enforce the ADR-002 invariant that ranking cannot widen the admissible set."""
    supplied = [candidate.candidate_id for candidate in candidates]
    returned = [candidate.candidate_id for candidate in ranked]
    if sorted(returned) != sorted(supplied):
        raise RankingContractError(
            "ranker must return a permutation of its candidates; "
            f"supplied {sorted(supplied)} and received {sorted(returned)}"
        )
    return tuple(ranked)


class LexicographicPlanRanker:
    """The original hand-authored objective, preserved exactly as the default.

    Prefers the shortest plan, then the least consequential side effects, then the
    fewest approvals.  The final term is a tie-break on capability id: it carries no
    judgement and exists only to make the choice deterministic, which is precisely why
    it is the term a learned ranker should replace first.
    """

    ranker_id = "lexicographic"
    ranker_version = "1.0"

    def rank(
        self, candidates: Sequence[PlanCandidate], *, goal: DomainGoal
    ) -> tuple[PlanCandidate, ...]:
        return tuple(sorted(candidates, key=self.sort_key))

    @staticmethod
    def sort_key(candidate: PlanCandidate) -> tuple[int, int, int, tuple[str, ...]]:
        return (
            len(candidate.steps),
            candidate.side_effect_score,
            candidate.approval_count,
            candidate.capability_ids,
        )


class EpisodeInformedRanker:
    """Prefers capability sequences that worked on problems shaped like this one.

    The first learned ranker, and deliberately the dumbest thing that could be called
    learning: it looks up prior episodes on comparable problems and prefers sequences
    with successful precedent, falling back to the base ordering wherever precedent is
    absent or contradictory.

    With no matching episodes it reduces exactly to its base ranker, so introducing it
    cannot make selection worse before it has anything to learn from.  It reorders the
    candidates it is given and cannot widen the admissible set (ADR-002).
    """

    ranker_id = "episode-informed"
    ranker_version = "1.0"

    def __init__(
        self,
        retriever: Any,
        *,
        context: Any = None,
        base: PlanRanker | None = None,
        limit: int = 5,
        minimum_similarity: float = 0.5,
    ) -> None:
        self.retriever = retriever
        self.context = context
        self.base = base or LexicographicPlanRanker()
        self.limit = limit
        self.minimum_similarity = minimum_similarity

    def rank(
        self, candidates: Sequence[PlanCandidate], *, goal: DomainGoal
    ) -> tuple[PlanCandidate, ...]:
        ordered = self.base.rank(candidates, goal=goal)
        precedent = self.precedent(ordered, goal=goal)
        if not any(precedent.values()):
            return ordered
        position = {candidate.candidate_id: index for index, candidate in enumerate(ordered)}
        return tuple(
            sorted(
                ordered,
                key=lambda candidate: (
                    -precedent[candidate.candidate_id],
                    position[candidate.candidate_id],
                ),
            )
        )

    def precedent(
        self, candidates: Sequence[PlanCandidate], *, goal: DomainGoal
    ) -> dict[str, float]:
        """Score each candidate by how its capability sequence has previously fared.

        Exposed separately from `rank` so the signal can be inspected and logged: a
        selection whose reasoning cannot be read back is not auditable.
        """
        from .fingerprint import fingerprint

        episodes = self.retriever.similar(
            fingerprint(goal, self.context),
            limit=self.limit,
            minimum_similarity=self.minimum_similarity,
        )
        scores = {candidate.candidate_id: 0.0 for candidate in candidates}
        for candidate in candidates:
            sequence = list(candidate.capability_ids)
            for episode in episodes:
                if not episode.informative or episode.chosen_capability_ids != sequence:
                    continue
                # Weighted by similarity: a closer problem is stronger evidence.
                scores[candidate.candidate_id] += (
                    episode.similarity if episode.succeeded else -episode.similarity
                )
        return scores
