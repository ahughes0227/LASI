"""Run fresh deterministic model floors against evaluator-separated splits."""

from __future__ import annotations

import json
from pathlib import Path

from services.benchmarks import (
    run_digit_reference,
    run_pjme_reference,
    run_titanic_reference,
)

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/cleanroom-baselines-v1"


def main() -> None:
    results = [
        run_titanic_reference(
            SPLITS / "titanic/input/train.csv",
            SPLITS / "titanic/private_evaluation/validation.csv",
        ),
        run_pjme_reference(
            SPLITS / "pjme-hourly/input/train.csv",
            SPLITS / "pjme-hourly/private_evaluation/validation.csv",
        ),
        run_digit_reference(
            SPLITS / "digit-recognizer/input/train.csv",
            SPLITS / "digit-recognizer/private_evaluation/validation.csv",
        ),
    ]
    payload = [result.model_dump(mode="json") for result in results]
    output = SPLITS / "reference-results.json"
    if output.exists():
        output.chmod(0o644)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o444)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
