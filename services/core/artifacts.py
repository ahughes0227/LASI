"""Local MLflow-compatible artifact adapter with provenance and safety checks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from uuid import uuid4

from services.contracts import ArtifactRecord


class ArtifactPolicyError(ValueError):
    """Raised for artifact paths, names, or content that violate safety policy."""


@dataclass(frozen=True, slots=True)
class ArtifactRun:
    run_id: str
    artifact_root: Path


class ArtifactStore(Protocol):
    def start_run(
        self, run_name: str, tags: dict[str, str] | None = None
    ) -> AbstractContextManager[ArtifactRun]: ...

    def log_file(
        self,
        run: ArtifactRun,
        source: Path,
        *,
        artifact_type: str,
        artifact_path: str,
        **provenance: str | None,
    ) -> ArtifactRecord: ...

    def log_json(
        self,
        run: ArtifactRun,
        value: dict[str, Any],
        *,
        filename: str,
        artifact_type: str,
        **provenance: str | None,
    ) -> ArtifactRecord: ...


_SENSITIVE_FILENAME = re.compile(r"(?:^|[._-])(env|credentials?|config|private)(?:[._-]|$)", re.I)
_SECRET_CONTENT = re.compile(r"(?:api[_-]?key|access[_-]?key|password|secret|token)\s*[:=]", re.I)


class MlflowArtifactStore:
    """Stores artifacts locally using stable `runs:/` URIs.

    The adapter deliberately keeps bytes in the configured artifact root and
    exposes MLflow-style URIs; the operational database records the returned
    contract separately.
    """

    def __init__(self, root: Path, *, experiment_name: str = "lasi") -> None:
        self.root = root.resolve()
        self.experiment_name = experiment_name

    @contextmanager
    def start_run(self, run_name: str, tags: dict[str, str] | None = None) -> Iterator[ArtifactRun]:
        run_id = uuid4().hex
        artifact_root = self.root / self.experiment_name / run_id / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=False)
        metadata = {"run_name": run_name, "tags": tags or {}}
        (artifact_root.parent / "run.json").write_text(
            json.dumps(metadata, sort_keys=True), encoding="utf-8"
        )
        yield ArtifactRun(run_id=run_id, artifact_root=artifact_root)

    def log_file(
        self,
        run: ArtifactRun,
        source: Path,
        *,
        artifact_type: str,
        artifact_path: str,
        **provenance: str | None,
    ) -> ArtifactRecord:
        if not source.is_file():
            raise FileNotFoundError(f"artifact source does not exist: {source}")
        destination = self._destination(run, artifact_path)
        payload = source.read_bytes()
        self._validate_payload(destination.name, payload)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return self._record(run, artifact_path, artifact_type, payload, provenance)

    def log_bytes(
        self,
        run: ArtifactRun,
        value: bytes,
        *,
        filename: str,
        artifact_type: str,
        **provenance: str | None,
    ) -> ArtifactRecord:
        destination = self._destination(run, filename)
        self._validate_payload(destination.name, value)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value)
        return self._record(run, filename, artifact_type, value, provenance)

    def log_json(
        self,
        run: ArtifactRun,
        value: dict[str, Any],
        *,
        filename: str,
        artifact_type: str,
        **provenance: str | None,
    ) -> ArtifactRecord:
        return self.log_bytes(
            run,
            json.dumps(value, sort_keys=True, default=str).encode("utf-8"),
            filename=filename,
            artifact_type=artifact_type,
            **provenance,
        )

    def download(self, record: ArtifactRecord) -> Path:
        prefix = "runs:/"
        if not record.artifact_uri.startswith(prefix):
            raise ArtifactPolicyError(f"unsupported artifact URI: {record.artifact_uri}")
        run_id, relative = record.artifact_uri.removeprefix(prefix).split("/", 1)
        path = self.root / self.experiment_name / run_id / "artifacts" / relative
        if not path.is_file():
            raise FileNotFoundError(f"artifact bytes missing: {record.artifact_uri}")
        return path

    @staticmethod
    def _safe_relative(value: str) -> PurePosixPath:
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or re.match(r"^[A-Za-z]:", value)
        ):
            raise ArtifactPolicyError(f"artifact path must be safe and relative: {value}")
        return path

    def _destination(self, run: ArtifactRun, artifact_path: str) -> Path:
        relative = self._safe_relative(artifact_path)
        destination = (run.artifact_root / Path(*relative.parts)).resolve()
        if run.artifact_root.resolve() not in destination.parents:
            raise ArtifactPolicyError(f"artifact path escapes run root: {artifact_path}")
        return destination

    @staticmethod
    def _validate_payload(filename: str, payload: bytes) -> None:
        if _SENSITIVE_FILENAME.search(filename):
            raise ArtifactPolicyError(f"sensitive artifact filename is not allowed: {filename}")
        text = payload.decode("utf-8", errors="ignore")
        if _SECRET_CONTENT.search(text):
            raise ArtifactPolicyError("artifact content appears to contain a secret")

    @staticmethod
    def _record(
        run: ArtifactRun,
        artifact_path: str,
        artifact_type: str,
        payload: bytes,
        provenance: dict[str, str | None],
    ) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=f"artifact-{uuid4().hex}",
            artifact_uri=f"runs:/{run.run_id}/{artifact_path}",
            artifact_type=artifact_type,
            checksum=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            immutable=True,
            **{key: value for key, value in provenance.items() if value is not None},
        )
