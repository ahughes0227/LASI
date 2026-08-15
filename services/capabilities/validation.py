"""Structural package validation and governed registration."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from services.contracts import (
    ApprovalRecord,
    CapabilityBuildPlan,
    CapabilityRegistrationProposal,
    CapabilityResearchDecision,
    CapabilityResolution,
    CapabilitySpec,
    CapabilityValidation,
    Provenance,
)

_REQUIRED_FILES = (
    "capability.yaml",
    "contract/input.schema.json",
    "contract/output.schema.json",
    "implementation/pipeline.yaml",
    "evaluation/eval.yaml",
    "provenance/resolution.yaml",
    "provenance/build-plan.yaml",
    "provenance/research-decisions.yaml",
    "README.md",
)

ContractT = TypeVar("ContractT", bound=BaseModel)


class CapabilityPackageValidator:
    def validate(self, package_root: str | Path) -> CapabilityValidation:
        root = Path(package_root).resolve()
        errors: list[str] = []
        checks = {"fixed_shell_complete": all((root / item).is_file() for item in _REQUIRED_FILES)}
        if not checks["fixed_shell_complete"]:
            errors.append("fixed capability shell is incomplete")
        capability = self._load(root / "capability.yaml", CapabilitySpec, errors)
        plan = self._load(root / "provenance/build-plan.yaml", CapabilityBuildPlan, errors)
        resolution = self._load(root / "provenance/resolution.yaml", CapabilityResolution, errors)
        checks["manifest_valid"] = capability is not None
        checks["build_plan_valid"] = plan is not None
        checks["dedup_resolution_attached"] = bool(
            plan and resolution and plan.resolution.resolution_id == resolution.resolution_id
        )
        checks["manifest_matches_plan"] = bool(
            capability
            and plan
            and (
                capability.capability_id == plan.capability.capability_id
                or (
                    plan.resolution.action == "extend"
                    and capability.capability_id in plan.resolution.selected_capability_ids
                )
            )
        )
        if not checks["manifest_matches_plan"]:
            errors.append("capability manifest does not match its build plan")
        checks["contracts_valid"] = all(
            self._valid_json(root / name, errors)
            for name in ("contract/input.schema.json", "contract/output.schema.json")
        )
        test_refs = sorted(str(path.relative_to(root)) for path in root.glob("tests/**/test_*.py"))
        checks["tests_present"] = bool(test_refs)
        if not test_refs:
            errors.append("no executable capability tests found")
        evaluation_refs: list[str] = []
        evaluation_path = root / "evaluation/eval.yaml"
        evaluation = (
            yaml.safe_load(evaluation_path.read_text(encoding="utf-8"))
            if evaluation_path.is_file()
            else {}
        )
        checks["evaluation_cases_present"] = bool(
            isinstance(evaluation, dict) and evaluation.get("cases")
        )
        if checks["evaluation_cases_present"]:
            evaluation_refs.append(str(evaluation_path.relative_to(root)))
        else:
            errors.append("capability evaluation has no cases")
        research = root / "provenance/research-decisions.yaml"
        research_value = (
            yaml.safe_load(research.read_text(encoding="utf-8")) if research.is_file() else {}
        )
        needs_research = bool(plan and plan.research_questions)
        raw_decisions = (
            research_value.get("decisions", []) if isinstance(research_value, dict) else []
        )
        valid_decisions = True
        for index, decision in enumerate(raw_decisions):
            try:
                CapabilityResearchDecision.model_validate(decision)
            except Exception as exc:
                errors.append(f"invalid research decision {index}: {exc}")
                valid_decisions = False
        has_research = bool(raw_decisions) and valid_decisions
        checks["research_gaps_resolved"] = not needs_research or has_research
        if not checks["research_gaps_resolved"]:
            errors.append("unresolved research questions remain")
        checks["dependency_graph_valid"] = bool(
            capability and capability.capability_id not in capability.capability_dependencies
        )
        package_hash = hash_package(root) if root.exists() else "sha256:missing"
        return CapabilityValidation(
            validation_id=f"capability-validation-{uuid4().hex}",
            build_id=plan.build_id if plan else "unknown",
            capability_id=capability.capability_id if capability else root.name,
            package_hash=package_hash,
            checks=checks,
            test_refs=test_refs,
            evaluation_refs=evaluation_refs,
            errors=errors,
            created_at=datetime.now(UTC),
            provenance=Provenance(source_path=str(root), content_hash=package_hash),
        )

    @staticmethod
    def _load(path: Path, contract: type[ContractT], errors: list[str]) -> ContractT | None:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            return contract.model_validate(value)
        except Exception as exc:  # Pydantic/YAML errors become structured validation evidence.
            errors.append(f"invalid {path.name}: {exc}")
            return None

    @staticmethod
    def _valid_json(path: Path, errors: list[str]) -> bool:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("type") != "object":
                raise ValueError("contract schema must describe an object")
            return True
        except Exception as exc:
            errors.append(f"invalid {path.name}: {exc}")
            return False


class CapabilityRegistrar:
    """Create a proposal, then register only with explicit shared-toolbox approval."""

    def propose(
        self,
        package_root: str | Path,
        plan: CapabilityBuildPlan,
        validation: CapabilityValidation,
    ) -> CapabilityRegistrationProposal:
        root = Path(package_root).resolve()
        if not validation.passed:
            raise ValueError("capability validation must pass before registration proposal")
        if validation.build_id != plan.build_id or validation.package_hash != hash_package(root):
            raise ValueError("validation does not match the current capability package")
        proposal = CapabilityRegistrationProposal(
            proposal_id=f"capability-registration-{uuid4().hex}",
            build_id=plan.build_id,
            capability_id=plan.capability.capability_id,
            capability_version=plan.capability.version,
            package_path=str(root),
            package_hash=validation.package_hash,
            resolution_ref="provenance/resolution.yaml",
            validation_ref="provenance/validation.yaml",
            registration_scope=plan.registration_scope,
            created_at=datetime.now(UTC),
            provenance=Provenance(
                source_records=[plan.resolution.resolution_id, validation.validation_id],
                content_hash=validation.package_hash,
            ),
        )
        (root / "provenance/validation.yaml").write_text(
            yaml.safe_dump(validation.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        (root / "provenance/registration-proposal.yaml").write_text(
            yaml.safe_dump(proposal.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        return proposal

    def register_shared(
        self,
        proposal: CapabilityRegistrationProposal,
        approval: ApprovalRecord,
    ) -> CapabilitySpec:
        if approval.proposal_id != proposal.proposal_id:
            raise PermissionError("approval does not match capability registration proposal")
        if approval.action_type != "update_toolbox":
            raise PermissionError("shared capability registration requires update_toolbox approval")
        if approval.approval_status != "approved" or not approval.approved_by:
            raise PermissionError("shared capability registration requires explicit human approval")
        root = Path(proposal.package_path).resolve()
        if hash_package(root) != proposal.package_hash:
            raise PermissionError("capability package changed after validation")
        value = yaml.safe_load((root / "capability.yaml").read_text(encoding="utf-8"))
        capability = CapabilitySpec.model_validate(value).model_copy(
            update={"lifecycle": "approved"}
        )
        registration = {
            "proposal": proposal.model_dump(mode="json"),
            "approval_id": approval.approval_id,
            "approved_by": approval.approved_by,
            "registered_at": datetime.now(UTC).isoformat(),
        }
        (root / "provenance/registration.yaml").write_text(
            yaml.safe_dump(registration, sort_keys=False), encoding="utf-8"
        )
        (root / "capability.yaml").write_text(
            yaml.safe_dump(capability.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        return capability


def hash_package(root: str | Path) -> str:
    base = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(item for item in base.rglob("*") if item.is_file()):
        relative = path.relative_to(base).as_posix()
        if relative in {
            "provenance/registration.yaml",
            "provenance/registration-proposal.yaml",
            "provenance/validation.yaml",
        }:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"
