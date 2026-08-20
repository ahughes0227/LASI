"""Contracts for comparing ranker variants against recorded episodes."""

from __future__ import annotations

from pydantic import Field

from services.contracts.models import StrictModel


class RankerVariant(StrictModel):
    """One selection policy to evaluate.

    `kind` names a policy this repository implements.  It is deliberately not an import
    path: a config file that could name any callable would be a way to execute arbitrary
    code through configuration, which is the same rule the component registry enforces.
    """

    name: str
    kind: str
    minimum_similarity: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=5, ge=1)


class VariantOutcome(StrictModel):
    """How one variant chose, over one set of replayed decisions."""

    name: str
    ranker_id: str
    ranker_version: str
    decisions: int = Field(default=0, ge=0)
    #: Decisions where more than one plan was admissible.  Everything else is a forced
    #: move and says nothing about the policy, so the two are counted separately.
    real_choices: int = Field(default=0, ge=0)
    #: Where this variant chose differently from the lexicographic default.
    differed_from_default: int = Field(default=0, ge=0)

    @property
    def divergence_rate(self) -> float:
        """Share of real choices where this variant departed from the default.

        Not a quality measure. It says how much a variant *does*, which is the
        prerequisite for asking whether what it does is any good.
        """
        if not self.real_choices:
            return 0.0
        return self.differed_from_default / self.real_choices


class SweepResult(StrictModel):
    variants: list[VariantOutcome] = Field(default_factory=list)

    @property
    def comparable(self) -> bool:
        """Whether every variant saw the same decisions.

        A comparison across different decision sets measures the sets, not the policies.
        """
        counts = {variant.decisions for variant in self.variants}
        return len(counts) <= 1
