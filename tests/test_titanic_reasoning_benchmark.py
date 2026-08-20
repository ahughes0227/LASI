"""Regression tests for the frozen Titanic reasoning scorecard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from services.benchmarks.reasoning_scorecard import (
    TitanicReasoningBenchmarkRun,
    compare_titanic_reasoning_runs,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tests/fixtures/titanic_reasoning/baseline-v1.json"
PROJECT_ROOT = ROOT / "projects/kaggle-titanic-naive"


def _baseline() -> TitanicReasoningBenchmarkRun:
    return TitanicReasoningBenchmarkRun.model_validate_json(
        BASELINE_PATH.read_text(encoding="utf-8")
    )


def _candidate(**updates: object) -> TitanicReasoningBenchmarkRun:
    value = _baseline().model_dump(mode="json")
    value.update(
        {
            "run_id": "candidate-run",
            "system_revision": "candidate-revision",
            "wall_clock": {
                "status": "measured",
                "wall_clock_seconds": 90.0,
                "source_reference": "runtime://candidate-run",
            },
            "token_usage": {
                "status": "reported",
                "input_tokens": 800,
                "output_tokens": 200,
                "cached_input_tokens": 100,
                "total_tokens": 1000,
                "source_reference": "runtime://candidate-run/usage",
            },
        }
    )
    value.update(updates)
    return TitanicReasoningBenchmarkRun.model_validate(value)


def test_legacy_baseline_is_frozen_to_the_existing_titanic_evidence() -> None:
    baseline = _baseline()
    metrics = json.loads(
        (PROJECT_ROOT / "30_evidence/metrics/titanic-title-family-logistic-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert baseline.reasoning_accuracy == pytest.approx(4 / 6)
    assert baseline.local_holdout_accuracy.value == metrics["evaluation"]["primary_value"]
    assert baseline.public_accuracy.value == 0.77511
    assert "0.78229" in (PROJECT_ROOT / "40_output/recommendation.md").read_text()


def test_legacy_missing_speed_and_tokens_are_not_reported_as_zero() -> None:
    baseline = _baseline()

    assert baseline.wall_clock.status == "not_available"
    assert baseline.wall_clock.wall_clock_seconds is None
    assert baseline.token_usage.status == "not_available"
    assert baseline.token_usage.total_tokens is None
    assert baseline.token_usage.unavailable_action_count == 3


def test_scorecard_reports_accuracy_improvement_without_inventing_legacy_efficiency() -> None:
    baseline = _baseline()
    checks = baseline.model_dump(mode="json")["reasoning_checks"]
    checks[4]["passed"] = True
    candidate = _candidate(reasoning_checks=checks)

    comparison = compare_titanic_reasoning_runs(baseline, candidate)

    assert comparison.reasoning_accuracy.improved is True
    assert comparison.reasoning_accuracy.delta == pytest.approx(1 / 6)
    assert comparison.local_holdout_accuracy.delta == 0
    assert comparison.public_accuracy.delta == 0
    assert comparison.wall_clock_seconds.status == "not_comparable"
    assert comparison.total_tokens.status == "not_comparable"


def test_scorecard_compares_speed_and_tokens_once_both_runs_have_receipts() -> None:
    baseline = _candidate(
        run_id="measured-baseline",
        wall_clock={
            "status": "measured",
            "wall_clock_seconds": 120.0,
            "source_reference": "runtime://baseline",
        },
        token_usage={
            "status": "reported",
            "input_tokens": 1000,
            "output_tokens": 300,
            "cached_input_tokens": 0,
            "total_tokens": 1300,
            "source_reference": "runtime://baseline/usage",
        },
    )
    candidate = _candidate()

    comparison = compare_titanic_reasoning_runs(baseline, candidate)

    assert comparison.wall_clock_seconds.delta == -30
    assert comparison.wall_clock_seconds.improved is True
    assert comparison.total_tokens.delta == -300
    assert comparison.total_tokens.improved is True


def test_benchmark_refuses_noncomparable_evidence_packets() -> None:
    with pytest.raises(ValueError, match="evidence_packet_hash"):
        compare_titanic_reasoning_runs(
            _baseline(), _candidate(evidence_packet_hash="changed-evidence")
        )


def test_reported_tokens_require_an_authoritative_exact_receipt() -> None:
    value = _candidate().model_dump(mode="json")
    value["token_usage"]["total_tokens"] = 999

    with pytest.raises(ValidationError, match="total_tokens"):
        TitanicReasoningBenchmarkRun.model_validate(value)
