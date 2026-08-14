from __future__ import annotations

# fmt: off

import csv
import hashlib
from pathlib import Path
from uuid import uuid4

from datetime import UTC, datetime

from services.contracts import ChallengeSpec, PredictionArtifact, SubmissionValidation

# ruff: noqa: E501, I001


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_submission(
    challenge: ChallengeSpec,
    artifact: PredictionArtifact,
    path: str | Path,
    *,
    expected_ids: set[str] | None = None,
) -> SubmissionValidation:
    """Validate a prediction file without reading hidden labels."""
    file_path = Path(path).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    observed_columns: list[str] = []
    observed_rows = 0
    ids: list[str] = []
    try:
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            observed_columns = list(reader.fieldnames or [])
            for row in reader:
                observed_rows += 1
                ids.extend(row.get(column, "") for column in challenge.identifier_columns)
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"unable to read submission: {exc}")

    expected = [*challenge.identifier_columns, *challenge.prediction_columns]
    if observed_columns and observed_columns != expected:
        errors.append(f"columns do not match required schema: expected {expected}, got {observed_columns}")
    if artifact.row_count != observed_rows:
        errors.append(f"artifact row_count {artifact.row_count} does not match file row count {observed_rows}")
    if expected_ids is not None:
        actual = set(ids)
        expected_id_values = {str(value) for value in expected_ids}
        if len(ids) != len(actual):
            errors.append("identifier columns contain duplicate IDs")
        if actual != expected_id_values:
            errors.append("submission IDs are not exactly the expected test IDs")
    if any(not value for value in ids):
        errors.append("submission contains missing identifiers")
    return SubmissionValidation(
        validation_id=f"submission-validation-{uuid4().hex}",
        challenge_id=challenge.challenge_id,
        prediction_artifact_id=artifact.prediction_artifact_id,
        status="validated" if not errors else "rejected",
        expected_columns=expected,
        observed_columns=observed_columns,
        expected_row_count=len(expected_ids) if expected_ids is not None else None,
        observed_row_count=observed_rows,
        errors=errors,
        warnings=warnings,
        checksum=_sha256(file_path) if file_path.is_file() else None,
    )


def prediction_artifact_from_file(
    challenge: ChallengeSpec,
    path: str | Path,
    *,
    model_run_id: str,
    source_test_dataset_version: str,
    generating_tool: str,
    generating_tool_version: str,
    row_count: int,
) -> PredictionArtifact:
    """Create immutable metadata for a produced prediction file."""
    file_path = Path(path).resolve()
    return PredictionArtifact(
        prediction_artifact_id=f"prediction-{uuid4().hex}",
        challenge_id=challenge.challenge_id,
        model_run_id=model_run_id,
        source_test_dataset_version=source_test_dataset_version,
        row_count=row_count,
        identifier_columns=challenge.identifier_columns,
        prediction_columns=challenge.prediction_columns,
        prediction_dtype="string_or_numeric",
        row_order_policy="test_source_order",
        checksum=_sha256(file_path),
        generating_tool=generating_tool,
        generating_tool_version=generating_tool_version,
        artifact_uri=str(file_path),
        created_at=datetime.now(UTC),
    )
