"""Explicit, non-executable local format adapters."""
from __future__ import annotations

# fmt: off

import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ruff: noqa: E501


UNSAFE_SUFFIXES = {".pkl", ".pickle", ".joblib", ".ipynb", ".py", ".exe", ".dll", ".bin"}


@dataclass(frozen=True)
class SchemaInspection:
    format_id: str
    adapter_version: str
    source_path: str
    size_bytes: int
    media_type: str
    columns: tuple[str, ...] = ()
    inferred_types: dict[str, str] | None = None
    row_count: int | None = None
    warnings: tuple[str, ...] = ()
    schema_fingerprint: str = ""


class FormatAdapter:
    format_id = ""
    version = "1.0"
    extensions: frozenset[str] = frozenset()

    def inspect(self, path: Path, *, limit: int = 1000) -> SchemaInspection:
        raise NotImplementedError

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        raise NotImplementedError


def _fingerprint(columns: tuple[str, ...], types: dict[str, str]) -> str:
    import hashlib

    return hashlib.sha256(json.dumps([columns, types], sort_keys=True).encode()).hexdigest()


class DelimitedAdapter(FormatAdapter):
    def __init__(self, format_id: str, delimiter: str) -> None:
        self.format_id, self.delimiter = format_id, delimiter
        self.extensions = frozenset({f".{format_id}"})

    def inspect(self, path: Path, *, limit: int = 1000) -> SchemaInspection:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=self.delimiter)
            columns = tuple(reader.fieldnames or ())
            rows = []
            for row in reader:
                rows.append(row)
                if len(rows) >= limit:
                    break
        types = {column: _type_of([row.get(column) for row in rows]) for column in columns}
        return SchemaInspection(self.format_id, self.version, str(path), path.stat().st_size,
                                "text/csv", columns, types, None, (), _fingerprint(columns, types))

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=self.delimiter)
            batch: list[dict[str, Any]] = []
            for row in reader:
                batch.append(dict(row))
                if len(batch) == batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch


class JsonlAdapter(FormatAdapter):
    format_id, extensions = "jsonl", frozenset({".jsonl", ".ndjson"})

    def inspect(self, path: Path, *, limit: int = 1000) -> SchemaInspection:
        rows = list(_json_rows(path, limit))
        columns = tuple(sorted({key for row in rows for key in row}))
        types = {column: _type_of([row.get(column) for row in rows]) for column in columns}
        return SchemaInspection(self.format_id, self.version, str(path), path.stat().st_size,
                                "application/x-ndjson", columns, types, None, (), _fingerprint(columns, types))

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        batch: list[dict[str, Any]] = []
        for row in _json_rows(path, None):
            batch.append(row)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


class JsonAdapter(JsonlAdapter):
    format_id, extensions = "json", frozenset({".json"})

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else [value]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("JSON data must be an object or array of objects")
        for index in range(0, len(rows), batch_size):
            yield rows[index:index + batch_size]

    def inspect(self, path: Path, *, limit: int = 1000) -> SchemaInspection:
        rows = next(self.batches(path, batch_size=limit), [])
        columns = tuple(sorted({key for row in rows for key in row}))
        types = {column: _type_of([row.get(column) for row in rows]) for column in columns}
        return SchemaInspection(self.format_id, self.version, str(path), path.stat().st_size,
                                "application/json", columns, types, len(rows), (), _fingerprint(columns, types))


class BinaryInspectionAdapter(FormatAdapter):
    """Safe metadata-only adapter for non-tabular local media."""
    def __init__(self, format_id: str, extensions: set[str], media_type: str) -> None:
        self.format_id, self.extensions, self.media_type = format_id, frozenset(extensions), media_type

    def inspect(self, path: Path, *, limit: int = 1000) -> SchemaInspection:
        return SchemaInspection(self.format_id, self.version, str(path), path.stat().st_size, self.media_type)

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        yield [{"source_path": str(path), "size_bytes": path.stat().st_size}]


class YamlAdapter(JsonAdapter):
    format_id, extensions = "yaml", frozenset({".yaml", ".yml"})

    def batches(self, path: Path, *, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        import yaml

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else [value]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("YAML data must be an object or array of objects")
        yield from (rows[index:index + batch_size] for index in range(0, len(rows), batch_size))


class FormatRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, FormatAdapter] = {}
        self.register(DelimitedAdapter("csv", ","))
        self.register(DelimitedAdapter("tsv", "\t"))
        self.register(JsonlAdapter())
        self.register(JsonAdapter())
        self.register(YamlAdapter())
        self.register(BinaryInspectionAdapter("parquet", {".parquet"}, "application/vnd.apache.parquet"))
        self.register(BinaryInspectionAdapter("arrow", {".arrow", ".feather"}, "application/vnd.apache.arrow.file"))
        self.register(BinaryInspectionAdapter("numpy", {".npy", ".npz"}, "application/x-numpy"))
        self.register(BinaryInspectionAdapter("image", {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}, "image/*"))
        self.register(BinaryInspectionAdapter("audio", {".wav", ".flac", ".mp3"}, "audio/*"))
        self.register(BinaryInspectionAdapter("video", {".mp4", ".avi", ".mov"}, "video/*"))

    def register(self, adapter: FormatAdapter) -> None:
        if adapter.format_id in self._adapters:
            raise ValueError(f"format adapter already registered: {adapter.format_id}")
        self._adapters[adapter.format_id] = adapter

    def select(self, path: str | Path, format_id: str | None = None) -> FormatAdapter:
        source = Path(path)
        if source.suffix.lower() in UNSAFE_SUFFIXES:
            raise ValueError(f"unsafe format is blocked: {source.suffix.lower()}")
        if format_id:
            try:
                return self._adapters[format_id]
            except KeyError as exc:
                raise ValueError(f"unsupported format: {format_id}") from exc
        matches = [adapter for adapter in self._adapters.values() if source.suffix.lower() in adapter.extensions]
        if len(matches) != 1:
            raise ValueError(f"unsupported or ambiguous format: {source.name}")
        return matches[0]


def _json_rows(path: Path, limit: int | None) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("JSONL rows must be objects")
            yield value


def _type_of(values: list[Any]) -> str:
    present = [value for value in values if value not in (None, "")]
    if not present:
        return "unknown"
    if all(isinstance(value, bool) for value in present):
        return "boolean"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in present):
        return "numeric"
    return "categorical"
