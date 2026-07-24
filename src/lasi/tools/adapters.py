"""Framework-neutral dataset validation and characterization adapters."""

from collections import Counter
from pathlib import Path
from uuid import uuid4

from lasi.contracts import DatasetCharacterization, DatasetManifest
from lasi.contracts.models import CharacterizationProfile


def validate_dataset(manifest: DatasetManifest, base_path: str | Path | None = None) -> list[str]:
    """Return structural validation errors; an empty list means usable input."""
    errors: list[str] = []
    ids = [sample.sample_id for sample in manifest.samples]
    duplicates = [sample_id for sample_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate sample IDs: {', '.join(sorted(duplicates))}")
    declared = set((manifest.label_schema or {}).get("labels", []))
    valid_splits = {"train", "validation", "val", "test", "human_review"}
    root = Path(base_path) if base_path is not None else None
    for sample in manifest.samples:
        if sample.label is None:
            errors.append(f"sample {sample.sample_id} has no label")
        if declared and sample.label not in declared:
            errors.append(f"sample {sample.sample_id} has undeclared label {sample.label!r}")
        if sample.point_cloud_ref is None:
            errors.append(f"sample {sample.sample_id} has no point-cloud reference")
        elif root is not None and not (root / sample.point_cloud_ref).exists():
            errors.append(f"missing point-cloud reference: {sample.point_cloud_ref}")
        if sample.split is not None and sample.split not in valid_splits:
            errors.append(f"sample {sample.sample_id} has invalid split {sample.split!r}")
    return errors


def characterize_dataset(manifest: DatasetManifest) -> DatasetCharacterization:
    labels = Counter(str(sample.label) for sample in manifest.samples if sample.label is not None)
    missing: Counter[str] = Counter()
    for sample in manifest.samples:
        for field in ("label", "point_cloud_ref", "split"):
            if getattr(sample, field) is None:
                missing[field] += 1
    status = "complete" if not missing else "partial_success"
    return DatasetCharacterization(
        characterization_id=str(uuid4()),
        project_id=manifest.project_id,
        dataset_version_id=manifest.dataset_version_id,
        sample_size=len(manifest.samples),
        class_balance=dict(labels),
        missingness_summary=dict(missing),
        primitive_profile=CharacterizationProfile(
            summary="Manifest primitive profile",
            metrics={"sample_count": len(manifest.samples), "class_count": len(labels)},
        ),
        status=status,
    )
