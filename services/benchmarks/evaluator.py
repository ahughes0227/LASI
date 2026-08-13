from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from services.contracts import ChallengeSpec, EvaluationResult, EvaluatorSpec, PredictionArtifact


@dataclass(frozen=True)
class Evaluator:
    spec: EvaluatorSpec
    score: Callable[[list[str], list[str]], float]


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Evaluator] = {}

    def register(self, evaluator: Evaluator) -> None:
        if evaluator.spec.evaluator_id in self._items:
            raise ValueError("evaluator already registered")
        self._items[evaluator.spec.evaluator_id] = evaluator

    def get(self, evaluator_id: str) -> Evaluator:
        try:
            return self._items[evaluator_id]
        except KeyError as exc:
            raise ValueError(f"evaluator is not registered: {evaluator_id}") from exc


class HiddenLabelEvaluator:
    """Evaluator-only boundary: hidden labels are supplied by the caller and never returned."""

    def __init__(self, registry: EvaluatorRegistry) -> None:
        self.registry = registry

    def evaluate(
        self,
        challenge: ChallengeSpec,
        artifact: PredictionArtifact,
        prediction_path: str | Path,
        hidden_labels: list[str],
        *,
        evaluator_id: str,
        evaluation_run_id: str,
    ) -> EvaluationResult:
        evaluator = self.registry.get(evaluator_id)
        predictions: list[str] = []
        with Path(prediction_path).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            column = challenge.prediction_columns[0]
            predictions = [row[column] for row in reader]
        if len(predictions) != len(hidden_labels):
            return EvaluationResult(
                evaluation_run_id=evaluation_run_id,
                challenge_id=challenge.challenge_id,
                prediction_artifact_id=artifact.prediction_artifact_id,
                evaluator_id=evaluator.spec.evaluator_id,
                evaluator_version=evaluator.spec.version,
                status="failed",
                primary_metric=evaluator.spec.primary_metric,
                sample_count=len(predictions),
            )
        score = evaluator.score(predictions, hidden_labels)
        return EvaluationResult(
            evaluation_run_id=evaluation_run_id,
            challenge_id=challenge.challenge_id,
            prediction_artifact_id=artifact.prediction_artifact_id,
            evaluator_id=evaluator.spec.evaluator_id,
            evaluator_version=evaluator.spec.version,
            status="succeeded",
            primary_metric=evaluator.spec.primary_metric,
            primary_value=score,
            sample_count=len(predictions),
        )
