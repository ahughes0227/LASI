"""Find what was tried on problems shaped like this one, and how it turned out.

An episode is a *view*: the planning decision joined to the execution it produced and the
outcome that execution reached.  It is assembled from the existing planning, assignment,
and attempt records rather than stored a second time, because a parallel episode store
would immediately be able to disagree with the tables it was copied from.
"""

from __future__ import annotations

from pydantic import Field

from services.contracts.models import StrictModel
from services.memory import OperationalMemory
from services.memory.models import PlanningEpisode

from .episodes import PlanningEpisodeRecorder, PlanOutcome
from .fingerprint import ProblemFingerprint


class Episode(StrictModel):
    """One prior attempt at a problem, with enough context to learn from it."""

    plan_id: str
    project_id: str
    fingerprint: ProblemFingerprint
    chosen_capability_ids: list[str] = Field(default_factory=list)
    status: str
    outcome: PlanOutcome
    similarity: float = Field(default=0.0, ge=0, le=1)

    @property
    def informative(self) -> bool:
        """Whether this episode says anything about how a plan performs.

        A plan that was never dispatched has no outcome to learn from.  Treating it as a
        neutral or poor result would let undispatched plans vote on future selection.
        """
        return self.outcome.attributable and self.outcome.resolved

    @property
    def succeeded(self) -> bool:
        return self.informative and self.outcome.assignment_status == "completed"


class EpisodeRetriever:
    """Reads prior episodes by problem shape."""

    def __init__(self, memory: OperationalMemory) -> None:
        self.memory = memory
        self.recorder = PlanningEpisodeRecorder(memory)

    def similar(
        self,
        fingerprint: ProblemFingerprint,
        *,
        limit: int = 5,
        minimum_similarity: float = 0.5,
        exclude_plan_ids: frozenset[str] = frozenset(),
    ) -> list[Episode]:
        """Prior episodes on comparable problems, most similar first.

        `minimum_similarity` is a floor rather than a ranking cut: a weakly related
        episode is not weak evidence, it is evidence about a different problem.
        """
        scored: list[Episode] = []
        for record in self.memory.list_all(PlanningEpisode):
            if record.plan_id in exclude_plan_ids or record.problem_fingerprint is None:
                continue
            stored = ProblemFingerprint.model_validate(record.problem_fingerprint)
            score = fingerprint.similarity(stored)
            if score < minimum_similarity:
                continue
            scored.append(self._episode(record, stored, score))
        scored.sort(key=lambda episode: (-episode.similarity, episode.plan_id))
        return scored[:limit]

    def _episode(
        self, record: PlanningEpisode, stored: ProblemFingerprint, score: float
    ) -> Episode:
        return Episode(
            plan_id=record.plan_id,
            project_id=record.project_id,
            fingerprint=stored,
            chosen_capability_ids=list(record.chosen_capability_ids),
            status=record.status,
            outcome=self.recorder.outcome(record.plan_id),
            similarity=score,
        )
