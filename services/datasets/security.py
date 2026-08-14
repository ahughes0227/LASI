from __future__ import annotations

# fmt: off

import hashlib
import os
import tarfile
import zipfile
from pathlib import Path

# ruff: noqa: E501, I001


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_archive(path: str | Path, destination: str | Path, *, max_members: int = 10000,
                         max_total_bytes: int = 2_000_000_000) -> list[Path]:
    source, root = Path(path).resolve(), Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    members: list[tuple[str, int, bool]] = []
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            zip_members = archive.infolist()
            for zip_info in zip_members:
                members.append((zip_info.filename, zip_info.file_size, zip_info.is_dir()))
            _check_members(members, max_members, max_total_bytes)
            for zip_info in zip_members:
                target = _contained(root, zip_info.filename)
                if zip_info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(zip_info) as src, target.open("wb") as dst:
                        dst.write(src.read(max_total_bytes + 1))
    elif source.suffix.lower() in {".tar", ".gz", ".tgz", ".bz2", ".xz"}:
        with tarfile.open(source) as archive:
            tar_members = archive.getmembers()
            for tar_info in tar_members:
                members.append((tar_info.name, tar_info.size, tar_info.isdir()))
                if tar_info.issym() or tar_info.islnk() or not (tar_info.isdir() or tar_info.isfile()):
                    raise ValueError(f"unsafe archive member: {tar_info.name}")
            _check_members(members, max_members, max_total_bytes)
            for tar_info in tar_members:
                target = _contained(root, tar_info.name)
                if tar_info.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    tar_source = archive.extractfile(tar_info)
                    if tar_source is None:
                        raise ValueError(f"unable to read archive member: {tar_info.name}")
                    with tar_source, target.open("wb") as dst:
                        dst.write(src.read(max_total_bytes + 1))
    else:
        raise ValueError("unsupported archive format")
    return [path for path in root.rglob("*") if path.is_file()]


def _contained(root: Path, member: str) -> Path:
    if os.path.isabs(member) or Path(member).drive or ".." in Path(member).parts:
        raise ValueError(f"archive path traversal blocked: {member}")
    target = (root / member).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"archive path escapes staging root: {member}")
    return target


def _check_members(members: list[tuple[str, int, bool]], max_members: int, max_total_bytes: int) -> None:
    if len(members) > max_members:
        raise ValueError("archive member count exceeds safety limit")
    if len({name for name, _, _ in members}) != len(members):
        raise ValueError("archive contains duplicate member names")
    if sum(size for _, size, _ in members) > max_total_bytes:
        raise ValueError("archive uncompressed size exceeds safety limit")
