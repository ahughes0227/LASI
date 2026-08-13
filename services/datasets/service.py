"""Point-cloud dataset operations backed by Parquet manifests and NPZ files.

The service deliberately returns the frozen LASI dataset contracts.  Validation
diagnostics are local operational records and do not become a second contract
boundary.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as parquet

from services.contracts import (
    ApprovalRecord,
    DatasetCharacterization,
    DatasetManifest,
    DatasetVersion,
)
from services.contracts.models import (
    CharacterizationProfile,
    DatasetFile,
    DatasetSample,
    Provenance,
)

_SPLITS = {"train", "validation", "test"}
_VERSION_STATUSES = {
    "draft",
    "validated",
    "characterized",
    "approved_for_training",
    "experimental",
    "benchmark",
    "production_candidate",
    "deprecated",
    "archived",
    "blocked",
}
_SAMPLE_FIELDS = set(DatasetSample.model_fields) - {"schema_version"}
_CHANGE_COMPARABILITY = {
    "initial_import": "unknown",
    "raw_data_addition": "partially_comparable",
    "targeted_data_addition": "partially_comparable",
    "label_correction": "partially_comparable",
    "label_policy_change": "not_comparable",
    "class_merge": "not_comparable",
    "class_split": "not_comparable",
    "synthetic_data_addition": "partially_comparable",
    "sample_removal": "partially_comparable",
    "deduplication": "partially_comparable",
    "metadata_enrichment": "comparable",
    "feature_addition": "comparable",
    "split_change": "partially_comparable",
    "benchmark_refresh": "not_comparable",
    "human_review_update": "partially_comparable",
}


@dataclass(slots=True)
class DatasetValidationResult:
    """Structured validation evidence for one manifest and its cloud files."""

    manifest: DatasetManifest
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    samples_checked: int = 0
    files_checked: int = 0


def load_parquet_manifest(
    path: str | Path,
    *,
    project_id: str,
    dataset_version_id: str,
    dataset_id: str | None = None,
    label_schema: dict[str, Any] | None = None,
) -> DatasetManifest:
    """Load one row per sample from a Parquet manifest into the frozen contract."""

    manifest_path = Path(path)
    table = parquet.read_table(manifest_path)
    rows = table.to_pylist()
    columns = set(table.column_names)
    unknown = sorted(columns - _SAMPLE_FIELDS)
    if unknown:
        raise ValueError(f"manifest contains unsupported columns: {', '.join(unknown)}")

    samples = [DatasetSample.model_validate(row) for row in rows]
    return DatasetManifest(
        project_id=project_id,
        dataset_version_id=dataset_version_id,
        dataset_id=dataset_id,
        file_list=[DatasetFile(path=manifest_path.name, media_type="application/parquet")],
        samples=samples,
        label_schema=label_schema,
        provenance=Provenance(source_path=str(manifest_path)),
    )


def validate_dataset(
    manifest: DatasetManifest,
    root: str | Path,
    *,
    allowed_labels: Iterable[str | int] | None = None,
    min_points: int = 1,
    max_points: int | None = None,
) -> DatasetValidationResult:
    """Validate manifest structure, referenced NPZ clouds, and declared checksums."""

    base = Path(root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    labels = set(allowed_labels) if allowed_labels is not None else _labels_from_schema(manifest)
    sample_ids: set[str] = set()
    files_checked = 0

    if not manifest.samples:
        errors.append("manifest contains no samples")

    for sample in manifest.samples:
        prefix = f"sample {sample.sample_id!r}"
        if sample.sample_id in sample_ids:
            errors.append(f"{prefix}: duplicate sample_id")
        sample_ids.add(sample.sample_id)
        if sample.label is None:
            errors.append(f"{prefix}: missing label")
        elif labels and sample.label not in labels:
            errors.append(f"{prefix}: label {sample.label!r} is not in label schema")
        if sample.split is not None and sample.split not in _SPLITS:
            errors.append(f"{prefix}: invalid split {sample.split!r}")
        if not sample.point_cloud_ref:
            errors.append(f"{prefix}: missing point_cloud_ref")
            continue

        cloud_path = _safe_path(base, sample.point_cloud_ref, errors, prefix)
        if cloud_path is None:
            continue
        files_checked += 1
        if cloud_path.suffix.lower() != ".npz":
            errors.append(f"{prefix}: point_cloud_ref must reference an .npz file")
            continue
        if not cloud_path.is_file():
            errors.append(f"{prefix}: point-cloud file does not exist: {sample.point_cloud_ref}")
            continue
        try:
            points = _read_points(cloud_path)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, EOFError) as exc:
            errors.append(f"{prefix}: invalid point-cloud file: {exc}")
            continue
        if points.shape[0] < min_points:
            errors.append(f"{prefix}: point count {points.shape[0]} is below {min_points}")
        if max_points is not None and points.shape[0] > max_points:
            errors.append(f"{prefix}: point count {points.shape[0]} exceeds {max_points}")
        if not np.isfinite(points).all():
            errors.append(f"{prefix}: coordinates contain non-finite values")

    for declared in manifest.file_list:
        file_path = _safe_path(base, declared.path, errors, "manifest file")
        if file_path is None or not file_path.is_file():
            errors.append(f"manifest file does not exist: {declared.path}")
            continue
        files_checked += 1
        if declared.size_bytes is not None and file_path.stat().st_size != declared.size_bytes:
            errors.append(f"file {declared.path!r}: size does not match manifest")
        if declared.checksum is not None and _sha256(file_path) != declared.checksum:
            errors.append(f"file {declared.path!r}: checksum does not match manifest")

    if not any(sample.split == "test" for sample in manifest.samples):
        warnings.append("manifest has no test split")
    return DatasetValidationResult(
        manifest=manifest,
        valid=not errors,
        errors=errors,
        warnings=warnings,
        samples_checked=len(manifest.samples),
        files_checked=files_checked,
    )


def create_dataset_version(
    manifest: DatasetManifest,
    *,
    manifest_path: str | Path,
    created_by: str,
    change_type: str = "initial_import",
    change_summary: str = "Initial dataset import",
    parent_version_id: str | None = None,
    created_because: str | None = None,
    status: str = "draft",
    role: str | None = None,
    benchmark: bool = False,
    approval_id: str | None = None,
    approval: ApprovalRecord | None = None,
) -> DatasetVersion:
    """Build version metadata only when the dataset change is authorized.

    Draft remains a version status, not an authorization bypass.
    """

    if not manifest.dataset_id:
        raise ValueError("manifest.dataset_id is required to create a dataset version")
    if status not in _VERSION_STATUSES:
        raise ValueError(f"unsupported dataset version status: {status}")
    if change_type not in _CHANGE_COMPARABILITY:
        raise ValueError(f"unsupported dataset change type: {change_type}")
    if benchmark and status != "benchmark":
        raise ValueError("benchmark versions must use status='benchmark'")
    _require_dataset_version_approval(manifest, approval, approval_id)
    assert approval is not None
    version = _version_from_id(manifest.dataset_version_id)
    return DatasetVersion(
        dataset_version_id=manifest.dataset_version_id,
        dataset_id=manifest.dataset_id,
        version=version,
        project_id=manifest.project_id,
        parent_version_id=parent_version_id,
        data_hash=_manifest_hash(manifest),
        manifest_path=str(manifest_path),
        created_at=datetime.now(UTC),
        created_by=created_by,
        change_type=change_type,
        change_summary=change_summary,
        created_because=created_because,
        # An initial import has no baseline against which results can be
        # compared.  Do not turn the lack of a parent into a comparability
        # assertion; the declared change type owns this semantic state.
        comparability_status=_CHANGE_COMPARABILITY[change_type],
        status=status,
        role=role,
        benchmark=benchmark,
        approval_id=approval.approval_id,
    )


def _require_dataset_version_approval(
    manifest: DatasetManifest,
    approval: ApprovalRecord | None,
    approval_id: str | None,
) -> None:
    """Require the current decision-system approval for every version creation."""

    if approval is None:
        raise PermissionError("an approved create_dataset_version authorization is required")
    if approval_id is not None and approval_id != approval.approval_id:
        raise ValueError("approval_id does not match approval.approval_id")
    if approval.project_id != manifest.project_id:
        raise PermissionError("approval belongs to a different project")
    if approval.action_type != "create_dataset_version":
        raise PermissionError("approval is not for create_dataset_version")
    if approval.approval_status != "approved":
        raise PermissionError("dataset-version approval is not approved")
    if approval.expires_at is not None and approval.expires_at < datetime.now(UTC):
        raise PermissionError("dataset-version approval has expired")


def characterize_dataset(
    manifest: DatasetManifest,
    root: str | Path,
    *,
    characterization_id: str,
) -> DatasetCharacterization:
    """Produce deterministic basic profiles from validated point-cloud samples."""

    result = validate_dataset(manifest, root)
    point_counts: list[int] = []
    extents: list[float] = []
    for sample in manifest.samples:
        if not sample.point_cloud_ref:
            continue
        path = _safe_path(Path(root).resolve(), sample.point_cloud_ref, [], sample.sample_id)
        if path is None or not path.is_file():
            continue
        try:
            points = _read_points(path)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, EOFError):
            continue
        point_counts.append(int(points.shape[0]))
        extents.append(float(np.ptp(points, axis=0).max()))

    counts = Counter(str(sample.label) for sample in manifest.samples)
    mean_points = float(np.mean(point_counts)) if point_counts else 0.0
    profile = CharacterizationProfile(
        summary="Basic point-cloud inventory",
        metrics={"mean_point_count": mean_points, "max_extent": max(extents, default=0.0)},
    )
    quality = CharacterizationProfile(
        metrics={
            "validation_error_count": len(result.errors),
            "validation_warning_count": len(result.warnings),
        },
        findings=result.errors + result.warnings,
    )
    return DatasetCharacterization(
        characterization_id=characterization_id,
        project_id=manifest.project_id,
        dataset_version_id=manifest.dataset_version_id,
        sample_size=len(manifest.samples),
        class_balance=dict(counts),
        missingness_summary={
            "missing_labels": sum(sample.label is None for sample in manifest.samples)
        },
        primitive_profile=CharacterizationProfile(
            metrics={
                "point_count_min": min(point_counts, default=0),
                "point_count_max": max(point_counts, default=0),
            }
        ),
        distribution_profile=profile,
        quality_profile=quality,
        identified_issues=result.errors,
        status="complete" if result.valid else "partial_success",
    )


def _read_points(path: Path) -> np.ndarray:
    with np.load(path, allow_pickle=False) as archive:
        for key in ("points", "coordinates", "xyz"):
            if key in archive:
                points = np.asarray(archive[key])
                break
        else:
            raise KeyError("NPZ must contain points, coordinates, or xyz")
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"coordinates must have shape (N, 3), got {points.shape}")
    return points


def _safe_path(base: Path, reference: str, errors: list[str], context: str) -> Path | None:
    candidate = Path(reference)
    if candidate.is_absolute():
        errors.append(f"{context}: absolute paths are not allowed")
        return None
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        errors.append(f"{context}: path escapes dataset root")
        return None
    return resolved


def _labels_from_schema(manifest: DatasetManifest) -> set[str | int]:
    if not manifest.label_schema:
        return set()
    values = manifest.label_schema.get("labels", manifest.label_schema.get("classes", []))
    return set(values) if isinstance(values, list) else set()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_hash(manifest: DatasetManifest) -> str:
    payload = manifest.model_dump(mode="json", exclude_none=True)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _version_from_id(version_id: str) -> str:
    return version_id.rsplit(":", 1)[-1] if ":" in version_id else version_id
