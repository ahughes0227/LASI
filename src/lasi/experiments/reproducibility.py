"""Stable reproducibility records for experiment audit and reruns."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from lasi.contracts import ExperimentPlan


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReproducibilityRecord:
    project_id: str
    experiment_id: str
    dataset_version: str
    manifest_hash: str
    config_hash: str
    tool_versions: dict[str, str]
    code_version: str | None
    random_seed: int | None
    execution_backend: str
    host_profile: str | None
    environment_snapshot: dict[str, Any]
    command: str | None
    artifact_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_reproducibility_record(
    plan: ExperimentPlan,
    *,
    manifest: Any,
    config: Any,
    tool_versions: Mapping[str, str],
    code_version: str | None = None,
    random_seed: int | None = None,
    environment_snapshot: Mapping[str, Any] | None = None,
    command: str | None = None,
    artifact_refs: tuple[str, ...] = (),
    experiment_id: str | None = None,
) -> ReproducibilityRecord:
    """Capture the minimum audit fields without inspecting or executing inputs."""

    return ReproducibilityRecord(
        project_id=plan.project_id,
        experiment_id=experiment_id or plan.experiment_plan_id,
        dataset_version=plan.dataset_version,
        manifest_hash=_digest(manifest),
        config_hash=_digest(config),
        tool_versions=dict(sorted(tool_versions.items())),
        code_version=code_version,
        random_seed=random_seed,
        execution_backend=plan.execution_backend,
        host_profile=plan.remote_host_profile,
        environment_snapshot=dict(environment_snapshot or {}),
        command=command,
        artifact_refs=tuple(artifact_refs),
    )
