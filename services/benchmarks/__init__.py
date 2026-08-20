"""Local, governed benchmark validation and hidden-label evaluation."""

from .clean_room import (
    CleanRoomPolicy,
    CleanRoomSplitReceipt,
    materialize_chronological_split,
    materialize_stratified_split,
)
from .domain_runtime import DomainRuntimeCaseResult, DomainRuntimeEvaluator
from .evaluator import EvaluatorRegistry, HiddenLabelEvaluator
from .reference_baselines import (
    ReferenceBaselineResult,
    run_digit_reference,
    run_pjme_reference,
    run_titanic_reference,
)
from .submissions import prediction_artifact_from_file, validate_submission

__all__ = [
    "CleanRoomPolicy",
    "CleanRoomSplitReceipt",
    "DomainRuntimeCaseResult",
    "DomainRuntimeEvaluator",
    "EvaluatorRegistry",
    "HiddenLabelEvaluator",
    "ReferenceBaselineResult",
    "materialize_chronological_split",
    "materialize_stratified_split",
    "prediction_artifact_from_file",
    "run_digit_reference",
    "run_pjme_reference",
    "run_titanic_reference",
    "validate_submission",
]
