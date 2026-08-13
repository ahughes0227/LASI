from __future__ import annotations

# fmt: off

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from services.datasets.security import sha256_file

# ruff: noqa: E501, I001


@dataclass(frozen=True)
class ChallengeWorkspace:
    root: Path
    input: Path
    working: Path
    artifacts: Path
    submission: Path
    private_evaluation: Path
    logs: Path

    @classmethod
    def create(cls, root: str | Path) -> ChallengeWorkspace:
        parent = Path(root).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        base = parent / f"challenge-{uuid4().hex}"
        paths = {name: base / name for name in ("input", "working", "artifacts", "submission", "private_evaluation", "logs")}
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=False)
        return cls(base, **paths)

    def ingest(self, sources: list[str | Path]) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for source in sources:
            source_path = Path(source).resolve()
            target = (self.input / source_path.name).resolve()
            if self.input not in target.parents:
                raise ValueError("input path escapes workspace")
            shutil.copy2(source_path, target)
            target.chmod(0o444)
            hashes[str(target)] = sha256_file(target)
        return hashes
