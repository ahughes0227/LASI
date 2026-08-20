"""Contracts for LM-backed reasoning and its evaluation.

No DSPy type appears here or in any LASI contract.  DSPy is one way to implement and
optimise a program; the system's vocabulary must outlive that choice (ADR-005).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from services.contracts.models import StrictModel

#: A newly optimised program is a challenger until it has been evaluated and approved.
#: There is deliberately no transition that a program can make on the strength of its
#: own score; promotion is a governed action.
ProgramStanding = Literal["baseline", "challenger", "champion", "rejected"]


class ReasoningCapabilitySpec(StrictModel):
    """Identity of one LM-backed reasoning program.

    Named `ReasoningCapability` rather than `Capability` because LASI already has
    capabilities, and they mean something else: a semantic registry entry describing what
    the system can do (ADR-001).  This is an implementation kind such an entry may
    declare, never a redefinition of it.
    """

    program_id: str
    program_version: str
    capability_id: str
    rubric_id: str
    rubric_version: str
    standing: ProgramStanding = "baseline"
    #: Hash of the program's compiled artefact.  Approval binds to this, so an approval
    #: cannot be reused for a program that has since changed.
    package_hash: str | None = None


class EvaluationCase(StrictModel):
    """One scored example, drawn from a recorded episode rather than authored.

    Cases come from what actually happened.  Hand-written cases measure agreement with
    their author, which is not the same as being right.
    """

    case_id: str
    diagnostic_packet_id: str
    project_id: str
    #: Evidence references the review is expected to ground itself in.
    expected_evidence_refs: list[str] = Field(default_factory=list)
    #: Whether the episode this case came from actually succeeded.  A case drawn from a
    #: failure is still a case: it should not be scored as if the outcome were good.
    outcome_succeeded: bool = False


class CriterionScore(StrictModel):
    criterion_id: str
    satisfied: bool
    required: bool
    detail: str | None = None


class CaseScore(StrictModel):
    case_id: str
    criteria: list[CriterionScore] = Field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        """A case passes only when every required criterion holds.

        Optional criteria are recorded but do not gate: they describe quality, and
        treating them as failures would make the metric reward verbosity.
        """
        if self.error is not None:
            return False
        return all(score.satisfied for score in self.criteria if score.required)


class EvaluationResult(StrictModel):
    """How one program scored over one dataset."""

    program_id: str
    program_version: str
    rubric_id: str
    rubric_version: str
    scores: list[CaseScore] = Field(default_factory=list)

    @property
    def case_count(self) -> int:
        return len(self.scores)

    @property
    def passed_count(self) -> int:
        return sum(score.passed for score in self.scores)

    @property
    def pass_rate(self) -> float:
        if not self.scores:
            return 0.0
        return self.passed_count / len(self.scores)


class ChallengerComparison(StrictModel):
    """Baseline against challenger, on the same cases.

    `improved` is not permission to deploy.  It is one input to a governed promotion,
    and is deliberately conservative: a challenger that merely ties does not win, and a
    comparison over too few cases does not count as evidence at all.
    """

    baseline: EvaluationResult
    challenger: EvaluationResult
    #: Below this, a difference in pass rate is noise dressed as a result.
    minimum_cases: int = Field(default=5, ge=1)

    @property
    def comparable(self) -> bool:
        return (
            self.baseline.case_count == self.challenger.case_count
            and self.baseline.case_count >= self.minimum_cases
        )

    @property
    def delta(self) -> float:
        return self.challenger.pass_rate - self.baseline.pass_rate

    @property
    def improved(self) -> bool:
        return self.comparable and self.delta > 0

    @property
    def verdict(self) -> str:
        if not self.comparable:
            return "insufficient_evidence"
        if self.delta > 0:
            return "challenger_better"
        if self.delta < 0:
            return "challenger_worse"
        return "no_difference"
