"""Materialize evaluator-separated splits from official Kaggle raw inputs."""

from __future__ import annotations

import json
from pathlib import Path

from services.benchmarks import (
    materialize_chronological_split,
    materialize_stratified_split,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/kaggle"
SPLITS = ROOT / "data/splits/cleanroom-baselines-v1"
SEED = 20260820


def main() -> None:
    receipts = [
        materialize_stratified_split(
            benchmark_id="titanic-cleanroom-v1",
            source=RAW / "titanic/extracted/train.csv",
            official_test=RAW / "titanic/extracted/test.csv",
            destination=SPLITS / "titanic",
            target_column="Survived",
            validation_fraction=0.2,
            random_seed=SEED,
        ),
        materialize_chronological_split(
            benchmark_id="pjme-hourly-cleanroom-v1",
            source=RAW / "hourly-energy-consumption/extracted/PJME_hourly.csv",
            destination=SPLITS / "pjme-hourly",
            time_column="Datetime",
            validation_rows=720,
        ),
        materialize_stratified_split(
            benchmark_id="digit-recognizer-cleanroom-v1",
            source=RAW / "digit-recognizer/extracted/train.csv",
            official_test=RAW / "digit-recognizer/extracted/test.csv",
            destination=SPLITS / "digit-recognizer",
            target_column="label",
            validation_fraction=0.2,
            random_seed=SEED,
        ),
    ]
    payload = [receipt.model_dump(mode="json") for receipt in receipts]
    receipt_path = SPLITS / "split-receipts.json"
    if receipt_path.exists():
        receipt_path.chmod(0o644)
    receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    receipt_path.chmod(0o444)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
