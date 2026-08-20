"""Score a reasoning program against the rubric that already governs its capability.

The metric is not invented here.  `ReasoningRubric` already defines what an acceptable
result looks like for a capability, and the runtime already accepts or rejects agent
results against it.  A separate optimisation metric would let a program score well while
producing results the runtime rejects.
"""

from __future__ import annotations

from services.contracts import DiagnosticPacket, ReasoningRubric, ScientistReview

from .models import CaseScore, CriterionScore, EvaluationCase, EvaluationResult
from .programs import ReasoningProgram, ReasoningScientistProvider

#: Criteria whose satisfaction a machine can check.  `judgment` criteria are recorded as
#: unevaluated rather than guessed at: scoring them with a heuristic would report a
#: number nobody measured, which is the same failure the token rule exists to prevent.
CHECKABLE_MODES = frozenset({"deterministic", "evidentiary"})


def score_review(
    review: ScientistReview, rubric: ReasoningRubric, case: EvaluationCase
) -> CaseScore:
    """Check one review against the rubric's checkable criteria."""
    scores: list[CriterionScore] = []
    for criterion in rubric.criteria:
        if criterion.evaluation_mode not in CHECKABLE_MODES:
            scores.append(
                CriterionScore(
                    criterion_id=criterion.criterion_id,
                    satisfied=True,
                    required=False,
                    detail="judgment criterion: not machine-checkable, not scored",
                )
            )
            continue
        satisfied, detail = _check(criterion.criterion_id, review, case)
        scores.append(
            CriterionScore(
                criterion_id=criterion.criterion_id,
                satisfied=satisfied,
                required=criterion.required,
                detail=detail,
            )
        )
    return CaseScore(case_id=case.case_id, criteria=scores)


def _check(criterion_id: str, review: ScientistReview, case: EvaluationCase) -> tuple[bool, str]:
    """Evidentiary checks: is the conclusion grounded in evidence that exists?

    Deliberately shallow.  These check that a review is *answerable*, not that it is
    correct; correctness is what the critic and the eventual outcome decide.
    """
    if not review.primary_diagnosis.strip():
        return False, "no diagnosis offered"
    if not review.evidence_references and not review.supporting_evidence:
        return False, "diagnosis is not grounded in any evidence reference"
    if case.expected_evidence_refs:
        cited = set(review.evidence_references) | set(review.supporting_evidence)
        missing = sorted(set(case.expected_evidence_refs) - cited)
        if missing:
            return False, f"did not cite available evidence: {', '.join(missing)}"
    if not review.recommended_next_action.strip():
        return False, "no next action recommended"
    return True, "grounded and actionable"


class ProgramEvaluator:
    """Runs a program over a dataset and scores each case."""

    def __init__(self, rubric: ReasoningRubric) -> None:
        self.rubric = rubric

    def evaluate(
        self,
        program: ReasoningProgram,
        provider: ReasoningScientistProvider,
        cases: list[EvaluationCase],
        packets: dict[str, DiagnosticPacket],
    ) -> EvaluationResult:
        scores: list[CaseScore] = []
        for case in cases:
            packet = packets.get(case.diagnostic_packet_id)
            if packet is None:
                scores.append(
                    CaseScore(case_id=case.case_id, error="diagnostic packet not available")
                )
                continue
            try:
                review = provider.review(packet)
            except Exception as exc:
                # A program that raises has failed the case.  Recording it as an error
                # rather than letting it abort the run keeps one bad case from hiding
                # every other result.
                scores.append(CaseScore(case_id=case.case_id, error=str(exc)))
                continue
            scores.append(score_review(review, self.rubric, case))
        return EvaluationResult(
            program_id=program.program_id,
            program_version=program.program_version,
            rubric_id=self.rubric.rubric_id,
            rubric_version=self.rubric.version,
            scores=scores,
        )
