"""Structural identity of a problem, for finding what was tried on problems like it.

Retrieval keys on the *shape* of the goal rather than its prose.  Two projects described
in different words but asking for the same predicates are the same problem for planning
purposes; two projects described identically but asking for different predicates are not.
Matching on description would get both cases wrong.
"""

from __future__ import annotations

from hashlib import sha256

from pydantic import Field

from services.contracts.models import StrictModel
from services.domain import DomainPredicate

from .domain_models import DomainGoal


class ProblemContext(StrictModel):
    """What distinguishes a problem beyond its goal predicates.

    Supplied by the caller rather than read from the database, so that planning stays a
    pure function of its inputs and can be tested without a store.
    """

    problem_type: str | None = None
    modality: str | None = None
    #: Which scaffold revision produced the workspace.  Carried so that a comparison
    #: across benches is visible as such instead of being silently averaged in.
    scaffold_revision: str | None = None


class ProblemFingerprint(StrictModel):
    """A comparable summary of what a goal is asking for."""

    digest: str
    #: Sorted `subject.predicate.operator` triples.  Values are deliberately excluded:
    #: "reach accuracy >= 0.8" and "reach accuracy >= 0.9" are the same kind of problem,
    #: and treating them as unrelated would defeat retrieval on the cases that matter.
    goal_shape: list[str] = Field(default_factory=list)
    problem_type: str | None = None
    modality: str | None = None
    scaffold_revision: str | None = None

    def similarity(self, other: ProblemFingerprint) -> float:
        """Jaccard overlap of goal shape, gated on problem type and modality.

        Returns 0 when problem type or modality disagree: a tabular classification result
        is not evidence about a vision forecasting problem however similar the predicates
        look, and a retrieval that blurred the two would be worse than none.
        """
        if self.problem_type and other.problem_type and self.problem_type != other.problem_type:
            return 0.0
        if self.modality and other.modality and self.modality != other.modality:
            return 0.0
        mine, theirs = set(self.goal_shape), set(other.goal_shape)
        if not mine or not theirs:
            return 0.0
        return len(mine & theirs) / len(mine | theirs)

    def same_bench(self, other: ProblemFingerprint) -> bool:
        """Whether both problems were posed on the same scaffold revision."""
        return self.scaffold_revision == other.scaffold_revision


def predicate_shape(predicate: DomainPredicate) -> str:
    return f"{predicate.subject}.{predicate.predicate}.{predicate.operator}"


def fingerprint(goal: DomainGoal, context: ProblemContext | None = None) -> ProblemFingerprint:
    """Summarise a goal into something comparable across projects."""
    resolved = context or ProblemContext()
    shape = sorted({predicate_shape(item) for item in goal.desired_state})
    material = "|".join(
        [
            ",".join(shape),
            resolved.problem_type or "",
            resolved.modality or "",
            resolved.scaffold_revision or "",
        ]
    )
    return ProblemFingerprint(
        digest=sha256(material.encode("utf-8")).hexdigest(),
        goal_shape=shape,
        problem_type=resolved.problem_type,
        modality=resolved.modality,
        scaffold_revision=resolved.scaffold_revision,
    )
