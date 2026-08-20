"""Contracts for what LASI records about a decision."""

from __future__ import annotations

from pydantic import Field

from services.contracts.models import StrictModel


class PlanningTrace(StrictModel):
    """One planning decision, in the form a later comparison needs.

    Records the size of the admissible set alongside the chosen plan, because
    "the ranker picked this" means nothing without knowing what it picked from: a
    forced move and a preference are indistinguishable otherwise.
    """

    plan_id: str
    project_id: str
    goal_id: str
    status: str
    ranker_id: str
    ranker_version: str
    admissible_count: int = Field(ge=0)
    chosen_capability_ids: list[str] = Field(default_factory=list)
    rejected_capability_count: int = Field(default=0, ge=0)
    problem_digest: str | None = None
    scaffold_revision: str | None = None
    #: Per-candidate precedent scores, when a ranker consulted prior episodes.  This is
    #: the reasoning behind the selection; a choice whose basis is not recorded cannot
    #: be audited or compared against a different ranker.
    precedent: dict[str, float] = Field(default_factory=dict)

    @property
    def was_a_real_choice(self) -> bool:
        """Whether more than one plan was admissible."""
        return self.admissible_count > 1
