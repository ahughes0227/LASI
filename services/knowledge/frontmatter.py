"""Strict markdown frontmatter parsing and contract validation."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from yaml import YAMLError

from services.contracts import KnowledgeDocument

from .models import ParsedKnowledgeDocument

_ALLOWED_FIELDS = frozenset(KnowledgeDocument.model_fields) | {"epistemic_status"}


class FrontmatterError(ValueError):
    """Raised when a knowledge document cannot be safely registered."""


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse a YAML frontmatter block and return metadata plus markdown body."""
    if not text.startswith("---"):
        raise FrontmatterError("knowledge document must start with YAML frontmatter")
    lines = text.splitlines(keepends=True)
    closing = next(
        (index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None
    )
    if closing is None:
        raise FrontmatterError("knowledge document frontmatter is not closed")
    try:
        raw = yaml.safe_load("".join(lines[1:closing]))
    except YAMLError as exc:
        raise FrontmatterError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise FrontmatterError("knowledge frontmatter must be a YAML mapping")
    metadata = dict(raw)
    unknown = sorted(set(metadata) - _ALLOWED_FIELDS)
    if unknown:
        raise FrontmatterError(f"unsupported frontmatter fields: {', '.join(unknown)}")
    if "epistemic_status" in metadata:
        if "status" in metadata and metadata["status"] != metadata["epistemic_status"]:
            raise FrontmatterError("status and epistemic_status disagree")
        metadata["status"] = metadata.pop("epistemic_status")
    return metadata, "".join(lines[closing + 1 :])


def parse_document(path: Path, *, relative_to: Path | None = None) -> ParsedKnowledgeDocument:
    """Read, parse, and validate one markdown knowledge document."""
    try:
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        document_path = path
        if relative_to is not None:
            document_path = path.relative_to(relative_to)
        metadata["path"] = document_path.as_posix()
        document = KnowledgeDocument.model_validate(metadata)
    except (OSError, ValueError, ValidationError) as exc:
        if isinstance(exc, FrontmatterError):
            raise
        raise FrontmatterError(f"invalid knowledge document {path}: {exc}") from exc
    return ParsedKnowledgeDocument(document=document, body=body, path=path)
