"""Focused tests for the fixture-oriented point-cloud dataset service."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as parquet
import pytest

from lasi.contracts import ApprovalRecord
from lasi.datasets import (
    characterize_dataset,
    create_dataset_version,
    load_parquet_manifest,
    validate_dataset,
)


def _fixture(root: Path) -> Path:
    np.savez(root / "a.npz", points=np.zeros((3, 3), dtype=np.float32))
    parquet.write_table(
        pa.table(
            {
                "sample_id": ["a"],
                "label": ["scratch"],
                "point_cloud_ref": ["a.npz"],
                "split": ["test"],
            }
        ),
        root / "manifest.parquet",
    )
    return root / "manifest.parquet"


def test_parquet_manifest_validates_cloud_and_characterizes(tmp_path: Path) -> None:
    manifest = load_parquet_manifest(
        _fixture(tmp_path),
        project_id="p1",
        dataset_id="scratch",
        dataset_version_id="scratch:v0.1.0",
        label_schema={"labels": ["scratch", "non_scratch"]},
    )

    validation = validate_dataset(manifest, tmp_path)
    assert validation.valid
    characterization = characterize_dataset(manifest, tmp_path, characterization_id="c1")
    assert characterization.class_balance == {"scratch": 1}
    assert characterization.distribution_profile.metrics["mean_point_count"] == 3.0


def test_version_requires_approval_for_protected_status(tmp_path: Path) -> None:
    manifest = load_parquet_manifest(
        _fixture(tmp_path),
        project_id="p1",
        dataset_id="scratch",
        dataset_version_id="scratch:v1.0.0",
    )
    with pytest.raises(PermissionError):
        create_dataset_version(
            manifest,
            manifest_path="manifest.parquet",
            created_by="test",
            status="production_candidate",
        )


def test_version_requires_approval_for_draft_status(tmp_path: Path) -> None:
    manifest = load_parquet_manifest(
        _fixture(tmp_path),
        project_id="p1",
        dataset_id="scratch",
        dataset_version_id="scratch:v0.1.0",
    )

    with pytest.raises(PermissionError, match="authorization is required"):
        create_dataset_version(manifest, manifest_path="manifest.parquet", created_by="test")


def test_version_accepts_current_matching_approval(tmp_path: Path) -> None:
    manifest = load_parquet_manifest(
        _fixture(tmp_path),
        project_id="p1",
        dataset_id="scratch",
        dataset_version_id="scratch:v0.1.0",
    )
    approval = ApprovalRecord(
        approval_id="approval-1",
        project_id="p1",
        action_type="create_dataset_version",
        risk_level="high",
        requested_by="operator",
        approved_by="reviewer",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )

    version = create_dataset_version(
        manifest,
        manifest_path="manifest.parquet",
        created_by="test",
        approval=approval,
    )

    assert version.approval_id == "approval-1"


@pytest.mark.parametrize(
    ("approval_status", "action_type", "expires_at", "project_id", "message"),
    [
        ("pending", "create_dataset_version", None, "p1", "not approved"),
        ("approved", "modify_labels", None, "p1", "not for create_dataset_version"),
        (
            "approved",
            "create_dataset_version",
            datetime.now(UTC) - timedelta(seconds=1),
            "p1",
            "expired",
        ),
        ("approved", "create_dataset_version", None, "other", "different project"),
    ],
)
def test_version_rejects_invalid_approval(
    tmp_path: Path,
    approval_status: str,
    action_type: str,
    expires_at: datetime | None,
    project_id: str,
    message: str,
) -> None:
    manifest = load_parquet_manifest(
        _fixture(tmp_path),
        project_id="p1",
        dataset_id="scratch",
        dataset_version_id="scratch:v0.1.0",
    )
    approval = ApprovalRecord(
        approval_id="approval-1",
        project_id=project_id,
        action_type=action_type,
        risk_level="high",
        requested_by="operator",
        approved_by="reviewer",
        approval_status=approval_status,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )

    with pytest.raises(PermissionError, match=message):
        create_dataset_version(
            manifest,
            manifest_path="manifest.parquet",
            created_by="test",
            approval=approval,
        )


def test_validation_rejects_bad_coordinates(tmp_path: Path) -> None:
    manifest_path = _fixture(tmp_path)
    np.savez(tmp_path / "a.npz", points=np.ones((2, 2)))
    manifest = load_parquet_manifest(
        manifest_path, project_id="p1", dataset_id="scratch", dataset_version_id="scratch:v0.1.0"
    )
    result = validate_dataset(manifest, tmp_path)
    assert not result.valid
    assert "coordinates" in result.errors[0]
