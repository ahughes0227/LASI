"""Capability-development resolution, shell, validation, and governance tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from services.capabilities import (
    CapabilityDevelopmentService,
    CapabilityPackageValidator,
    CapabilityRegistrar,
    CapabilityRegistry,
    CapabilityResolver,
)
from services.contracts import ApprovalRecord, CapabilitySpec


def _capability(capability_id: str, **changes: object) -> CapabilitySpec:
    values: dict[str, object] = {
        "capability_id": capability_id,
        "name": capability_id,
        "version": "1.0.0",
        "purpose": "Extract normalized tables from PDF documents",
        "accepts": ["document/pdf"],
        "produces": ["structured/table"],
        "operations": ["extract_tables"],
        "guarantees": ["preserve_provenance"],
        "lifecycle": "approved",
    }
    values.update(changes)
    return CapabilitySpec(**values)


def test_resolver_reuses_exact_contract() -> None:
    registry = CapabilityRegistry()
    registry.add(_capability("document.pdf.tables"))

    resolution = CapabilityResolver(registry).resolve(
        _capability("requested.tables", lifecycle="draft")
    )

    assert resolution.action == "reuse"
    assert resolution.selected_capability_ids == ["document.pdf.tables"]


def test_resolver_prefers_composition_when_operations_are_covered() -> None:
    registry = CapabilityRegistry()
    registry.add(
        _capability(
            "document.pdf.text",
            purpose="Transform PDF documents",
            produces=["document/pdf"],
            operations=["replace_text"],
            guarantees=[],
        )
    )
    registry.add(
        _capability(
            "document.pdf.images",
            purpose="Transform PDF documents",
            produces=["document/pdf"],
            operations=["replace_image"],
            guarantees=[],
        )
    )
    requested = _capability(
        "document.company_rebrand",
        purpose="Transform PDF documents",
        produces=["document/pdf"],
        operations=["replace_text", "replace_image"],
        guarantees=[],
        lifecycle="draft",
    )

    resolution = CapabilityResolver(registry).resolve(requested)

    assert resolution.action == "compose"
    assert set(resolution.selected_capability_ids) == {
        "document.pdf.text",
        "document.pdf.images",
    }


def test_explicit_exclusion_prevents_false_reuse() -> None:
    registry = CapabilityRegistry()
    registry.add(
        _capability(
            "document.pdf.text",
            purpose="Transform PDF documents",
            operations=["replace_text"],
            does_not=["replace_image"],
        )
    )
    requested = _capability(
        "document.pdf.image_transform",
        purpose="Transform PDF documents and images",
        operations=["replace_image"],
        lifecycle="draft",
    )

    resolution = CapabilityResolver(registry).resolve(requested)

    assert resolution.action != "reuse"


def test_extension_plan_targets_owner_and_records_dependent_impact() -> None:
    registry = CapabilityRegistry()
    registry.add(
        _capability(
            "document.pdf.transform",
            purpose="Transform PDF documents",
            produces=["document/pdf"],
            operations=["replace_text"],
            guarantees=[],
            provenance={"source_path": "capabilities/document.pdf.transform"},
        )
    )
    registry.add(
        _capability(
            "document.pdf.redact",
            purpose="Redact PDF documents",
            produces=["document/pdf"],
            operations=["redact_text"],
            guarantees=[],
            capability_dependencies=["document.pdf.transform"],
        )
    )
    requested = _capability(
        "document.pdf.rebrand",
        purpose="Transform PDF documents",
        produces=["document/pdf"],
        operations=["replace_text", "replace_image"],
        guarantees=[],
        lifecycle="draft",
    )

    plan = CapabilityDevelopmentService(registry).plan(requested)

    assert plan.resolution.action == "extend"
    assert plan.files_to_create == []
    assert plan.files_to_modify == ["capabilities/document.pdf.transform"]
    assert plan.affected_capability_ids == ["document.pdf.redact"]


def test_new_capability_scaffold_is_fixed_and_fails_closed_until_completed(
    tmp_path: Path,
) -> None:
    capability = _capability(
        "document.pdf.tables", lifecycle="draft", purpose="Infer tables from malformed documents"
    )
    service = CapabilityDevelopmentService(CapabilityRegistry())
    plan = service.plan(capability)
    package = service.scaffold(plan, tmp_path / "capabilities")

    assert plan.resolution.action == "new"
    assert (package / "provenance/resolution.yaml").is_file()
    assert (package / "implementation/custom").is_dir()
    validation = CapabilityPackageValidator().validate(package)
    assert not validation.passed
    assert not validation.checks["tests_present"]
    assert not validation.checks["evaluation_cases_present"]
    assert not validation.checks["research_gaps_resolved"]


def test_validated_package_proposes_registration_but_requires_approval(tmp_path: Path) -> None:
    capability = _capability("document.pdf.tables", lifecycle="draft")
    service = CapabilityDevelopmentService(CapabilityRegistry())
    plan = service.plan(capability)
    package = service.scaffold(plan, tmp_path / "capabilities")
    test_file = package / "tests/contract/test_contract.py"
    test_file.write_text("def test_contract():\n    assert True\n", encoding="utf-8")
    evaluation = yaml.safe_load((package / "evaluation/eval.yaml").read_text())
    evaluation["cases"] = [{"id": "simple-table", "expected": "structured/table"}]
    (package / "evaluation/eval.yaml").write_text(
        yaml.safe_dump(evaluation, sort_keys=False), encoding="utf-8"
    )
    (package / "provenance/research-decisions.yaml").write_text(
        yaml.safe_dump(
            {
                "decisions": [
                    {
                        "decision_id": "research-1",
                        "question": plan.research_questions[0],
                        "alternatives": ["bounded", "unbounded"],
                        "selected_approach": "bounded",
                        "rationale": ["preserves the execution boundary"],
                        "confidence": 0.9,
                        "sources": ["_architecture/16_CAPABILITY_DEVELOPMENT_SYSTEM.md"],
                        "created_at": datetime.now(UTC),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    validation = CapabilityPackageValidator().validate(package)
    assert validation.passed, validation.errors

    registrar = CapabilityRegistrar()
    proposal = registrar.propose(package, plan, validation)
    assert proposal.status == "pending_approval"
    assert (package / "provenance/registration-proposal.yaml").is_file()

    pending = ApprovalRecord(
        approval_id="approval-1",
        project_id="capability-system",
        proposal_id=proposal.proposal_id,
        action_type="update_toolbox",
        risk_level="high",
        requested_by="lasi-capability-builder",
        approval_status="pending",
        created_at=datetime.now(UTC),
    )
    with pytest.raises(PermissionError, match="explicit human approval"):
        registrar.register_shared(proposal, pending)

    approved = pending.model_copy(update={"approval_status": "approved", "approved_by": "owner"})
    registered = registrar.register_shared(proposal, approved)
    assert registered.lifecycle == "approved"
    assert (package / "provenance/registration.yaml").is_file()
