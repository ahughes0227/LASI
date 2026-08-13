"""Regression checks for Mercury's governed challenge records."""

import json
from pathlib import Path

from services.contracts import ChallengeSpec, DatasetManifest, DatasetVersion


def test_mercury_challenge_records_are_consistent() -> None:
    root = Path("projects/mercury/30_evidence")
    challenge = ChallengeSpec.model_validate(
        json.loads((root / "mercury-challenge-spec.json").read_text(encoding="utf-8"))
    )
    manifest = DatasetManifest.model_validate(
        json.loads((root / "mercury-store-sales-v1-manifest.json").read_text(encoding="utf-8"))
    )
    version = DatasetVersion.model_validate(
        json.loads(
            (root / "mercury-store-sales-v1-dataset-version.json").read_text(encoding="utf-8")
        )
    )

    assert challenge.project_id == manifest.project_id == version.project_id == "mercury"
    assert challenge.target_columns == ["sales"]
    assert challenge.identifier_columns == ["id"]
    assert version.dataset_version_id == manifest.dataset_version_id
    assert version.benchmark is True
    assert version.status == "benchmark"
    assert version.comparability_status == "unknown"
