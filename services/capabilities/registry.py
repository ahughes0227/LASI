"""Semantic capability registry used for discovery and deduplication."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from services.contracts import CapabilitySpec, Provenance


class CapabilityRegistry:
    """Explicit metadata inventory; executable bindings remain in component/tool registries."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], CapabilitySpec] = {}

    def add(self, capability: CapabilitySpec) -> None:
        key = (capability.capability_id, capability.version)
        if key in self._items:
            raise ValueError(
                f"capability already indexed: {capability.capability_id}@{capability.version}"
            )
        self._items[key] = capability

    def all(self, *, include_drafts: bool = False) -> tuple[CapabilitySpec, ...]:
        values = tuple(self._items.values())
        if not include_drafts:
            values = tuple(
                item for item in values if item.lifecycle in {"experimental", "approved"}
            )
        return tuple(sorted(values, key=lambda item: (item.capability_id, item.version)))

    def get(self, capability_id: str, version: str | None = None) -> CapabilitySpec:
        matches = [
            item
            for (item_id, item_version), item in self._items.items()
            if item_id == capability_id and (version is None or item_version == version)
        ]
        if not matches:
            raise ValueError(f"capability is not indexed: {capability_id}")
        return sorted(matches, key=lambda item: tuple(map(int, item.version.split("."))))[-1]

    def dependents(self, capability_id: str) -> tuple[CapabilitySpec, ...]:
        return tuple(
            item
            for item in self.all(include_drafts=True)
            if capability_id in item.capability_dependencies
        )

    @classmethod
    def discover(cls, root: str | Path) -> CapabilityRegistry:
        """Load fixed-shell manifests without importing generated implementation code."""
        registry = cls()
        base = Path(root)
        if not base.exists():
            return registry
        for path in sorted(base.glob("*/capability.yaml")):
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"capability manifest must be a mapping: {path}")
            registry.add(CapabilitySpec.model_validate(value))
        return registry

    def add_system_context(self, root: str | Path) -> None:
        """Index existing ICM capability descriptions as semantic discovery candidates."""
        base = Path(root)
        for path in sorted(base.glob("*.md")):
            if path.name == "README.md":
                continue
            text = path.read_text(encoding="utf-8").strip()
            purpose = " ".join(line.strip("# ") for line in text.splitlines() if line.strip())
            self.add(
                CapabilitySpec(
                    capability_id=f"icm.{path.stem}",
                    name=f"ICM {path.stem.replace('_', ' ').title()}",
                    version="1.0.0",
                    purpose=purpose,
                    operations=[path.stem],
                    execution_kind="opencode_skill",
                    lifecycle="approved",
                    provenance=Provenance(source_path=str(path)),
                )
            )
