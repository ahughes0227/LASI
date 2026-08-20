"""Deterministic split materialization for clean-room benchmark runs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, model_validator
from sklearn.model_selection import train_test_split

from services.contracts.models import StrictModel
from services.datasets.security import sha256_file


class CleanRoomPolicy(StrictModel):
    """Access policy presented to and enforced around a benchmark run."""

    prior_run_access: Literal["deny"] = "deny"
    network_access: Literal["deny"] = "deny"
    external_provider_access: Literal["deny"] = "deny"
    hidden_labels: Literal["evaluator_only"] = "evaluator_only"
    allowed_read_roots: list[str] = Field(min_length=1)
    forbidden_path_markers: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_history_boundaries(self) -> CleanRoomPolicy:
        required = {"projects", "mlruns", "mlartifacts", "reports"}
        normalized = {marker.strip("/") for marker in self.forbidden_path_markers}
        missing = required - normalized
        if missing:
            raise ValueError(
                "clean-room policy is missing historical result boundaries: "
                + ", ".join(sorted(missing))
            )
        return self


class CleanRoomSplitReceipt(StrictModel):
    benchmark_id: str
    split_kind: Literal["stratified", "chronological"]
    source_sha256: str
    train_sha256: str
    validation_sha256: str
    test_sha256: str | None = None
    train_rows: int = Field(gt=0)
    validation_rows: int = Field(gt=0)
    test_rows: int | None = Field(default=None, gt=0)
    random_seed: int | None = None
    cutoff: str | None = None


def materialize_stratified_split(
    *,
    benchmark_id: str,
    source: Path,
    destination: Path,
    target_column: str,
    validation_fraction: float,
    random_seed: int,
    official_test: Path | None = None,
) -> CleanRoomSplitReceipt:
    """Create a deterministic training input and evaluator-only validation file."""

    frame = pd.read_csv(source)
    if target_column not in frame:
        raise ValueError(f"target column is missing: {target_column}")
    train, validation = train_test_split(
        frame,
        test_size=validation_fraction,
        random_state=random_seed,
        stratify=frame[target_column],
    )
    train = train.sort_index(kind="stable")
    validation = validation.sort_index(kind="stable")
    return _write_split(
        benchmark_id=benchmark_id,
        split_kind="stratified",
        source=source,
        destination=destination,
        train=train,
        validation=validation,
        official_test=official_test,
        random_seed=random_seed,
    )


def materialize_chronological_split(
    *,
    benchmark_id: str,
    source: Path,
    destination: Path,
    time_column: str,
    validation_rows: int,
) -> CleanRoomSplitReceipt:
    """Create a past-only training input and evaluator-only future holdout."""

    frame = pd.read_csv(source)
    if time_column not in frame:
        raise ValueError(f"time column is missing: {time_column}")
    frame[time_column] = pd.to_datetime(frame[time_column], errors="raise")
    frame = frame.sort_values(time_column, kind="stable")
    if validation_rows <= 0 or validation_rows >= len(frame):
        raise ValueError("validation_rows must leave non-empty train and validation sets")
    train = frame.iloc[:-validation_rows]
    validation = frame.iloc[-validation_rows:]
    cutoff = str(train[time_column].max())
    receipt = _write_split(
        benchmark_id=benchmark_id,
        split_kind="chronological",
        source=source,
        destination=destination,
        train=train,
        validation=validation,
    )
    return receipt.model_copy(update={"cutoff": cutoff})


def _write_split(
    *,
    benchmark_id: str,
    split_kind: Literal["stratified", "chronological"],
    source: Path,
    destination: Path,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    official_test: Path | None = None,
    random_seed: int | None = None,
) -> CleanRoomSplitReceipt:
    input_root = destination / "input"
    evaluator_root = destination / "private_evaluation"
    input_root.mkdir(parents=True, exist_ok=True)
    evaluator_root.mkdir(parents=True, exist_ok=True)
    train_path = input_root / "train.csv"
    validation_path = evaluator_root / "validation.csv"
    _make_replaceable(train_path)
    _make_replaceable(validation_path)
    train.to_csv(train_path, index=False)
    validation.to_csv(validation_path, index=False)
    test_path: Path | None = None
    if official_test is not None:
        test_path = input_root / "test.csv"
        _make_replaceable(test_path)
        shutil.copy2(official_test, test_path)
    for path in (train_path, validation_path, test_path):
        if path is not None:
            path.chmod(0o444)
    return CleanRoomSplitReceipt(
        benchmark_id=benchmark_id,
        split_kind=split_kind,
        source_sha256=sha256_file(source),
        train_sha256=sha256_file(train_path),
        validation_sha256=sha256_file(validation_path),
        test_sha256=sha256_file(test_path) if test_path else None,
        train_rows=len(train),
        validation_rows=len(validation),
        test_rows=_csv_row_count(test_path) if test_path else None,
        random_seed=random_seed,
    )


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle) - 1


def _make_replaceable(path: Path) -> None:
    if path.exists():
        path.chmod(0o644)
