"""Semantic sidecar contracts and registry behavior."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from services.capabilities import CapabilityRegistry
from services.contracts import CapabilitySpec
from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainFact,
    DomainStateSnapshot,
)

ROOT = Path(__file__).parents[1]


def _capability(capability_id: str, version: str = "1.0.0") -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=capability_id,
        name=capability_id,
        version=version,
        purpose="A test capability",
        operations=["run"],
        lifecycle="draft",
    )


def _registry(*capabilities: CapabilitySpec) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for capability in capabilities:
        registry.add(capability)
    return registry


def _contract(capability_id: str = "alpha", **changes: object) -> CapabilityDomainContract:
    values: dict[str, object] = {
        "capability_id": capability_id,
        "capability_version": "1.0.0",
        "side_effect_class": "read",
        "provenance_refs": ["test"],
    }
    values.update(changes)
    return CapabilityDomainContract(**values)


def _snapshot(*predicates: str) -> DomainStateSnapshot:
    now = datetime.now(UTC)
    return DomainStateSnapshot(
        project_id="project-1",
        revision=1,
        created_at=now,
        facts=[
            DomainFact(
                fact_id=f"fact-{predicate}",
                project_id="project-1",
                subject="project",
                predicate=predicate,
                value=True,
                status="observed",
                confidence=1,
                evidence_refs=["test"],
                source="test",
                observed_at=now,
            )
            for predicate in predicates
        ],
    )


def test_registry_loads_matching_sidecar(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "domain-contract.yaml").write_text(
        """\
capability_id: alpha
capability_version: 1.0.0
preconditions: []
effects: []
invariants: []
side_effect_class: read
validation_capability_ids: []
provenance_refs: [test]
""",
        encoding="utf-8",
    )

    registry = CapabilityDomainRegistry(_registry(_capability("alpha")), tmp_path).discover()
    assert registry.get("alpha").capability_version == "1.0.0"


def test_registry_rejects_unknown_capability() -> None:
    with pytest.raises(ValueError, match="missing or version-mismatched"):
        CapabilityDomainRegistry.from_items(_registry(), [_contract()])


def test_registry_rejects_version_mismatch() -> None:
    with pytest.raises(ValueError, match="missing or version-mismatched"):
        CapabilityDomainRegistry.from_items(_registry(_capability("alpha", "2.0.0")), [_contract()])


def test_registry_rejects_unknown_validation_capability() -> None:
    contract = _contract("alpha", side_effect_class="update", validation_capability_ids=["missing"])
    with pytest.raises(ValueError, match="unknown capability"):
        CapabilityDomainRegistry.from_items(_registry(_capability("alpha")), [contract])


def test_mutating_contract_requires_validation() -> None:
    with pytest.raises(ValueError, match="require at least one validation"):
        _contract("alpha", side_effect_class="update")


def test_external_contract_requires_compensation() -> None:
    with pytest.raises(ValueError, match="require compensation"):
        _contract("alpha", side_effect_class="external", validation_capability_ids=["alpha"])


def test_eligible_filters_unsatisfied_preconditions() -> None:
    contracts = [
        _contract(
            "alpha",
            preconditions=[{"subject": "project", "predicate": "ready", "operator": "exists"}],
        ),
        _contract("beta"),
    ]
    registry = CapabilityDomainRegistry.from_items(
        _registry(_capability("alpha"), _capability("beta")), contracts
    )
    assert [item.capability_id for item in registry.eligible(_snapshot())] == ["beta"]


def test_eligible_output_is_sorted() -> None:
    registry = CapabilityDomainRegistry.from_items(
        _registry(_capability("zeta"), _capability("alpha")),
        [_contract("zeta"), _contract("alpha")],
    )
    assert [item.capability_id for item in registry.eligible(_snapshot())] == ["alpha", "zeta"]


def test_initial_sidecars_load_against_repository_capabilities() -> None:
    capability_registry = CapabilityRegistry.discover(ROOT / "capabilities")
    registry = CapabilityDomainRegistry(capability_registry, ROOT / "capabilities").discover()
    assert {item.capability_id for item in registry.all()} >= {
        "eda",
        "evaluation",
        "research",
        "modeling",
    }
