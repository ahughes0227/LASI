"""Shared rules for hashing fixed-shell packages reproducibly.

A package hash binds validation evidence and an approval to exact file content.
Editor, interpreter, and tool caches are not package content: they appear and
disappear as a side effect of running the package's own tests, so including
them makes a validated package fail its own registration hash check.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

#: Directory names that hold generated caches rather than package content.
EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
    }
)

#: File names and suffixes produced by interpreters, editors, and operating systems.
EXCLUDED_FILENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyd", ".pyo"})


def is_package_content(relative_path: Path) -> bool:
    """Return whether a package-relative path contributes to the package hash."""
    if EXCLUDED_DIRECTORIES.intersection(relative_path.parts[:-1]):
        return False
    if relative_path.name in EXCLUDED_FILENAMES:
        return False
    return relative_path.suffix not in EXCLUDED_SUFFIXES


def package_files(
    root: str | Path, *, excluded_relative_paths: frozenset[str] = frozenset()
) -> Iterator[tuple[str, Path]]:
    """Yield ``(posix_relative_path, absolute_path)`` for hashable package files.

    Results are sorted by relative path so the digest does not depend on
    filesystem ordering.  ``excluded_relative_paths`` removes the provenance
    artifacts that a package writes after its own hash is computed.
    """
    base = Path(root).resolve()
    entries: list[tuple[str, Path]] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if not is_package_content(relative):
            continue
        posix = relative.as_posix()
        if posix in excluded_relative_paths:
            continue
        entries.append((posix, path))
    entries.sort(key=lambda item: item[0])
    return iter(entries)
