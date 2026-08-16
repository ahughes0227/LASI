"""Fixed-shell validation and approval-bound component registration."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from uuid import uuid4

import yaml
from pydantic import BaseModel

from services.contracts import (
    ApprovalRecord,
    ComponentBuildPlan,
    ComponentRegistrationProposal,
    ComponentRegistrationRecord,
    ComponentResearchDecision,
    ComponentResolution,
    ComponentRuntimeSpec,
    ComponentSpec,
    ComponentValidation,
    Provenance,
)
from services.core import package_files

from .registry import ComponentHandler, ComponentRegistry

if TYPE_CHECKING:
    from services.memory import OperationalMemory
    from services.planner import PlannerCatalogBuilder

_REQUIRED_FILES = (
    "component.yaml",
    "contract/config.schema.json",
    "contract/input.schema.json",
    "contract/output.schema.json",
    "implementation/runtime.yaml",
    "evaluation/eval.yaml",
    "provenance/resolution.yaml",
    "provenance/build-plan.yaml",
    "provenance/research-decisions.yaml",
    "README.md",
)
ContractT = TypeVar("ContractT", bound=BaseModel)


class ComponentPackageValidator:
    def validate(self, package_root: str | Path) -> ComponentValidation:
        root = Path(package_root).resolve()
        errors: list[str] = []
        checks = {"fixed_shell_complete": all((root / item).is_file() for item in _REQUIRED_FILES)}
        if not checks["fixed_shell_complete"]:
            errors.append("fixed component shell is incomplete")
        component = self._load(root / "component.yaml", ComponentSpec, errors)
        plan = self._load(root / "provenance/build-plan.yaml", ComponentBuildPlan, errors)
        resolution = self._load(root / "provenance/resolution.yaml", ComponentResolution, errors)
        checks["manifest_valid"] = component is not None
        checks["build_plan_valid"] = plan is not None
        checks["resolution_attached"] = bool(
            plan and resolution and plan.resolution.resolution_id == resolution.resolution_id
        )
        checks["manifest_matches_plan"] = bool(
            component and plan and component.component_id == plan.component.component_id
        )
        if not checks["manifest_matches_plan"]:
            errors.append("component manifest does not match its build plan")
        checks["contracts_valid"] = all(
            self._valid_json(root / name, errors)
            for name in (
                "contract/config.schema.json",
                "contract/input.schema.json",
                "contract/output.schema.json",
            )
        )
        runtime = self._load_yaml(root / "implementation/runtime.yaml", errors)
        runtime_model = None
        if isinstance(runtime, dict):
            try:
                runtime_model = ComponentRuntimeSpec.model_validate(runtime)
            except Exception as exc:
                errors.append(f"invalid runtime declaration: {exc}")
        checks["runtime_matches_manifest"] = bool(
            component and runtime_model and runtime_model == component.runtime
        )
        if not checks["runtime_matches_manifest"]:
            errors.append("runtime declaration does not match component manifest")
        checks["granularity_declared"] = bool(
            component and component.responsibility and component.configuration_boundary is not None
        )
        if not checks["granularity_declared"]:
            errors.append(
                "component must declare one responsibility and its configuration boundary"
            )
        checks["tests_present"] = bool(list(root.glob("tests/**/test_*.py")))
        if not checks["tests_present"]:
            errors.append("no executable component tests found")
        evaluation = self._load_yaml(root / "evaluation/eval.yaml", errors)
        checks["evaluation_cases_present"] = bool(
            isinstance(evaluation, dict) and evaluation.get("cases")
        )
        if not checks["evaluation_cases_present"]:
            errors.append("component evaluation has no cases")
        research = self._load_yaml(root / "provenance/research-decisions.yaml", errors)
        raw_decisions = research.get("decisions", []) if isinstance(research, dict) else []
        valid_decisions = True
        for index, decision in enumerate(raw_decisions):
            try:
                ComponentResearchDecision.model_validate(decision)
            except Exception as exc:
                valid_decisions = False
                errors.append(f"invalid research decision {index}: {exc}")
        needs_research = bool(plan and plan.research_questions)
        checks["research_gaps_resolved"] = not needs_research or (
            bool(raw_decisions) and valid_decisions
        )
        if not checks["research_gaps_resolved"]:
            errors.append("unresolved research questions remain")
        checks["no_operation_selector"] = not _has_operation_selector(
            component.config_schema if component else {}
        )
        if not checks["no_operation_selector"]:
            errors.append("component configuration must not select unrelated operations")
        package_hash = hash_component_package(root) if root.exists() else "sha256:missing"
        return ComponentValidation(
            validation_id=f"component-validation-{uuid4().hex}",
            build_id=plan.build_id if plan else "unknown",
            component_id=component.component_id if component else root.name,
            package_hash=package_hash,
            checks=checks,
            test_refs=sorted(
                str(path.relative_to(root)) for path in root.glob("tests/**/test_*.py")
            ),
            evaluation_refs=["evaluation/eval.yaml"] if checks["evaluation_cases_present"] else [],
            errors=errors,
            created_at=datetime.now(UTC),
            provenance=Provenance(source_path=str(root), content_hash=package_hash),
        )

    @staticmethod
    def _load(path: Path, contract: type[ContractT], errors: list[str]) -> ContractT | None:
        try:
            return contract.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except Exception as exc:
            errors.append(f"invalid {path.name}: {exc}")
            return None

    @staticmethod
    def _load_yaml(path: Path, errors: list[str]) -> object:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            return value if value is not None else {}
        except Exception as exc:
            errors.append(f"invalid {path.name}: {exc}")
            return {}

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


class ComponentRegistrar:
    """Create proposals and register only with explicit toolbox approval."""

    def propose(
        self,
        package_root: str | Path,
        plan: ComponentBuildPlan,
        validation: ComponentValidation,
    ) -> ComponentRegistrationProposal:
        root = Path(package_root).resolve()
        if not validation.passed:
            raise ValueError("component validation must pass before registration proposal")
        if (
            validation.build_id != plan.build_id
            or validation.package_hash != hash_component_package(root)
        ):
            raise ValueError("validation does not match the current component package")
        proposal = ComponentRegistrationProposal(
            proposal_id=f"component-registration-{uuid4().hex}",
            build_id=plan.build_id,
            component_id=plan.component.component_id,
            component_version=plan.component.version,
            package_path=str(root),
            package_hash=validation.package_hash,
            resolution_ref="provenance/resolution.yaml",
            validation_ref="provenance/validation.yaml",
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
        proposal: ComponentRegistrationProposal,
        approval: ApprovalRecord,
        registry: ComponentRegistry,
        config_model: type[BaseModel],
        handler: ComponentHandler,
        *,
        planner_builder: PlannerCatalogBuilder | None = None,
        memory: OperationalMemory | None = None,
    ) -> ComponentRegistrationRecord:
        if approval.proposal_id != proposal.proposal_id:
            raise PermissionError("approval does not match component registration proposal")
        if approval.action_type != "update_toolbox":
            raise PermissionError("component registration requires update_toolbox approval")
        if approval.approval_status != "approved" or not approval.approved_by:
            raise PermissionError("component registration requires explicit human approval")
        root = Path(proposal.package_path).resolve()
        if hash_component_package(root) != proposal.package_hash:
            raise PermissionError("component package changed after validation")
        value = yaml.safe_load((root / "component.yaml").read_text(encoding="utf-8"))
        component = ComponentSpec.model_validate(value).model_copy(update={"lifecycle": "approved"})
        registry.register(component, config_model, handler, source_hash=component.source_hash)
        projection_status = "not_requested"
        projection_error = None
        if planner_builder is not None and memory is not None:
            try:
                planner_builder.persist(memory)
                projection_status = "succeeded"
            except Exception as exc:
                projection_status = "failed_stale"
                projection_error = str(exc)
        record = ComponentRegistrationRecord(
            registration_id=f"component-registration-record-{uuid4().hex}",
            proposal_id=proposal.proposal_id,
            component_id=component.component_id,
            component_version=component.version,
            package_hash=proposal.package_hash,
            planner_projection_status=projection_status,
            planner_projection_error=projection_error,
            created_at=datetime.now(UTC),
            provenance=Provenance(
                source_records=[proposal.proposal_id, approval.approval_id],
                content_hash=proposal.package_hash,
            ),
        )
        (root / "provenance/registration.yaml").write_text(
            yaml.safe_dump(record.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        return record


def hash_component_package(root: str | Path) -> str:
    digest = hashlib.sha256()
    excluded = frozenset(
        {
            "provenance/registration.yaml",
            "provenance/registration-proposal.yaml",
            "provenance/validation.yaml",
        }
    )
    for relative, path in package_files(root, excluded_relative_paths=excluded):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _has_operation_selector(schema: dict[str, object]) -> bool:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return False
    return any(name in {"operation", "operations", "action", "actions"} for name in properties)
