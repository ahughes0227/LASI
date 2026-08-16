"""Versioned semantic contracts for capabilities.

These contracts describe state requirements and effects; they do not bind or
execute capability implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from services.capabilities.registry import CapabilityRegistry
from services.contracts.models import StrictModel

from .models import DomainEffect, DomainPredicate, DomainStateSnapshot
from .predicates import PredicateEvaluator


class CapabilityDomainContract(StrictModel):
    """Preconditions, effects, and safety metadata for one capability version."""

    capability_id: str
    capability_version: str
    preconditions: list[DomainPredicate] = Field(default_factory=list)
    effects: list[DomainEffect] = Field(default_factory=list)
    invariants: list[DomainPredicate] = Field(default_factory=list)
    side_effect_class: Literal["none", "read", "create", "update", "delete", "external"]
    validation_capability_ids: list[str] = Field(default_factory=list)
    compensation_capability_id: str | None = None
    provenance_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_safety_requirements(self) -> CapabilityDomainContract:
        if self.side_effect_class in {"none", "read"} and self.compensation_capability_id:
            raise ValueError("none and read contracts cannot declare compensation")
        if (
            self.side_effect_class in {"update", "delete", "external"}
            and not self.validation_capability_ids
        ):
            raise ValueError(
                f"{self.side_effect_class} contracts require at least one validation capability"
            )
        if self.side_effect_class in {"delete", "external"} and not self.compensation_capability_id:
            raise ValueError(f"{self.side_effect_class} contracts require compensation")
        return self


class CapabilityDomainRegistry:
    """Authoritative inventory of capability semantic sidecars."""

    def __init__(self, capability_registry: CapabilityRegistry, root: str | Path) -> None:
        self.capability_registry = capability_registry
        self.root = Path(root)
        self._items: dict[str, CapabilityDomainContract] = {}

    def discover(self) -> CapabilityDomainRegistry:
        contracts = []
        if self.root.exists():
            for path in sorted(self.root.glob("*/domain-contract.yaml")):
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError(f"capability domain contract must be a mapping: {path}")
                try:
                    contracts.append(CapabilityDomainContract.model_validate(value))
                except Exception as exc:
                    raise ValueError(f"invalid capability domain contract: {path}: {exc}") from exc
        self._set_items(contracts)
        return self

    @classmethod
    def from_items(
        cls,
        capability_registry: CapabilityRegistry,
        contracts: list[CapabilityDomainContract],
    ) -> CapabilityDomainRegistry:
        registry = cls(capability_registry, Path("."))
        registry._set_items(contracts)
        return registry

    def get(self, capability_id: str) -> CapabilityDomainContract:
        try:
            return self._items[capability_id]
        except KeyError as exc:
            raise ValueError(f"capability domain contract is not indexed: {capability_id}") from exc

    def all(self) -> tuple[CapabilityDomainContract, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def eligible(self, snapshot: DomainStateSnapshot) -> tuple[CapabilityDomainContract, ...]:
        evaluator = PredicateEvaluator()
        return tuple(
            contract
            for contract in self.all()
            if all(
                result.satisfied
                for result in evaluator.evaluate_all(contract.preconditions, snapshot)
            )
        )

    def _set_items(self, contracts: list[CapabilityDomainContract]) -> None:
        self._validate_cross_references(contracts)
        self._items = {contract.capability_id: contract for contract in contracts}

    def _validate_cross_references(self, contracts: list[CapabilityDomainContract]) -> None:
        seen: set[str] = set()
        for contract in contracts:
            if contract.capability_id in seen:
                raise ValueError(f"duplicate capability domain contract: {contract.capability_id}")
            seen.add(contract.capability_id)
            try:
                capability = self.capability_registry.get(
                    contract.capability_id, contract.capability_version
                )
            except ValueError as exc:
                raise ValueError(
                    f"domain contract capability is missing or version-mismatched: "
                    f"{contract.capability_id}@{contract.capability_version}"
                ) from exc
            if capability.version != contract.capability_version:
                raise ValueError(
                    f"domain contract version mismatch: {contract.capability_id} "
                    f"expects {capability.version}, got {contract.capability_version}"
                )
            for referenced_id in [
                *contract.validation_capability_ids,
                *(
                    [contract.compensation_capability_id]
                    if contract.compensation_capability_id
                    else []
                ),
            ]:
                try:
                    self.capability_registry.get(referenced_id)
                except ValueError as exc:
                    raise ValueError(
                        f"domain contract references unknown capability: {referenced_id}"
                    ) from exc
