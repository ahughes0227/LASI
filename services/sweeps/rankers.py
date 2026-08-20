"""Build ranker variants from configuration, without letting configuration name code."""

from __future__ import annotations

from typing import Any

from services.planner import EpisodeInformedRanker, EpisodeRetriever, LexicographicPlanRanker
from services.planner.fingerprint import ProblemContext

from .models import RankerVariant


class UnknownRankerError(ValueError):
    """The configuration named a policy this repository does not implement."""


def build_ranker(
    variant: RankerVariant,
    *,
    retriever: EpisodeRetriever | None = None,
    context: ProblemContext | None = None,
) -> Any:
    """Resolve a variant to a ranker.

    The mapping is explicit rather than dynamic.  Resolving an import path from config
    would let a YAML file execute arbitrary code, which is precisely what the component
    registry exists to prevent; a sweep runner is not the place to make an exception.
    """
    if variant.kind == "lexicographic":
        return LexicographicPlanRanker()
    if variant.kind == "episode_informed":
        if retriever is None:
            raise UnknownRankerError("episode_informed requires a retriever")
        return EpisodeInformedRanker(
            retriever,
            context=context,
            limit=variant.limit,
            minimum_similarity=variant.minimum_similarity,
        )
    raise UnknownRankerError(f"unknown ranker kind: {variant.kind!r}")
