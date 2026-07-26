"""Local, governed benchmark validation and hidden-label evaluation."""

from .evaluator import EvaluatorRegistry, HiddenLabelEvaluator
from .submissions import prediction_artifact_from_file, validate_submission

__all__ = [
    "EvaluatorRegistry",
    "HiddenLabelEvaluator",
    "prediction_artifact_from_file",
    "validate_submission",
]
