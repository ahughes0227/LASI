"""LM-backed reasoning: programs, their evaluation, and governed promotion."""

from .challengers import REQUIRED_ACTION, PromotionError, package_hash, promote
from .evaluation import ProgramEvaluator, score_review
from .models import (
    CaseScore,
    ChallengerComparison,
    CriterionScore,
    EvaluationCase,
    EvaluationResult,
    ProgramStanding,
    ReasoningCapabilitySpec,
)
from .programs import ReasoningProgram, ReasoningScientistProvider

__all__ = [
    "REQUIRED_ACTION",
    "CaseScore",
    "ChallengerComparison",
    "CriterionScore",
    "EvaluationCase",
    "EvaluationResult",
    "ProgramEvaluator",
    "ProgramStanding",
    "PromotionError",
    "ReasoningCapabilitySpec",
    "ReasoningProgram",
    "ReasoningScientistProvider",
    "package_hash",
    "promote",
    "score_review",
]
