"""Clean-room benchmark split and access-policy regressions."""

import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError
from services.benchmarks import (
    CleanRoomPolicy,
    ReferenceBaselineResult,
    materialize_chronological_split,
    materialize_stratified_split,
)

ROOT = Path(__file__).resolve().parents[1]


def test_policy_fails_without_historical_result_boundaries(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="historical result boundaries"):
        CleanRoomPolicy(
            allowed_read_roots=[str(tmp_path / "input")],
            forbidden_path_markers=["projects"],
        )


def test_baseline_suite_denies_history_and_has_unique_source_hashes() -> None:
    suite = json.loads(
        (ROOT / "configs/benchmarks/cleanroom-suite-v1.json").read_text(encoding="utf-8")
    )
    policy = CleanRoomPolicy.model_validate(suite["access_policy"])
    benchmarks = suite["benchmarks"]

    assert policy.prior_run_access == "deny"
    assert policy.hidden_labels == "evaluator_only"
    assert len({item["benchmark_id"] for item in benchmarks}) == 3
    assert len({item["source_train_sha256"] for item in benchmarks}) == 3
    assert {item["modality"] for item in benchmarks} == {"tabular", "time_series", "vision"}


def test_stratified_split_is_deterministic_and_hides_validation(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    pd.DataFrame({"id": range(20), "feature": range(20), "target": [0, 1] * 10}).to_csv(
        source, index=False
    )
    first = materialize_stratified_split(
        benchmark_id="classification-v1",
        source=source,
        destination=tmp_path / "first",
        target_column="target",
        validation_fraction=0.2,
        random_seed=7,
    )
    second = materialize_stratified_split(
        benchmark_id="classification-v1",
        source=source,
        destination=tmp_path / "second",
        target_column="target",
        validation_fraction=0.2,
        random_seed=7,
    )

    assert first.train_sha256 == second.train_sha256
    assert first.validation_sha256 == second.validation_sha256
    assert not (tmp_path / "first/input/validation.csv").exists()
    assert (tmp_path / "first/private_evaluation/validation.csv").exists()


def test_time_series_split_is_strictly_chronological(tmp_path: Path) -> None:
    source = tmp_path / "series.csv"
    pd.DataFrame(
        {
            "time": ["2026-01-03", "2026-01-01", "2026-01-04", "2026-01-02"],
            "target": [3, 1, 4, 2],
        }
    ).to_csv(source, index=False)
    receipt = materialize_chronological_split(
        benchmark_id="forecast-v1",
        source=source,
        destination=tmp_path / "split",
        time_column="time",
        validation_rows=2,
    )

    train = pd.read_csv(tmp_path / "split/input/train.csv")
    validation = pd.read_csv(tmp_path / "split/private_evaluation/validation.csv")
    assert train["target"].tolist() == [1, 2]
    assert validation["target"].tolist() == [3, 4]
    assert receipt.cutoff == "2026-01-02 00:00:00"


def test_reference_result_cannot_claim_prior_run_evidence() -> None:
    with pytest.raises(ValidationError, match="prior_run_refs"):
        ReferenceBaselineResult(
            benchmark_id="vision-v1",
            metric="accuracy",
            direction="maximize",
            value=0.9,
            train_rows=100,
            validation_rows=20,
            wall_clock_seconds=1,
            prior_run_refs=["projects/old-run/metrics.json"],
        )
