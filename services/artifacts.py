"""Content-addressed promotion of files produced inside operator workspaces."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

from .contracts import ArtifactReceipt


class ArtifactPolicyError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)

    def promote(self, path: str, workspace: Path) -> ArtifactReceipt:
        source = Path(path)
        if not source.is_absolute():
            source = workspace / source
        resolved_workspace = workspace.resolve()
        resolved = source.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(resolved_workspace):
            raise ArtifactPolicyError("artifact must be a regular file inside the workspace")
        if source.is_symlink():
            raise ArtifactPolicyError("artifact symlinks are not accepted")
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        target = self.root / digest[:2] / digest
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            shutil.copyfile(resolved, temporary)
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        return ArtifactReceipt(
            digest=digest,
            uri=target.resolve().as_uri(),
            size_bytes=target.stat().st_size,
        )
