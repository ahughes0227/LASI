"""Fixed-shell validation and proposal creation for workflow packages."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel

from services.contracts import (
    Provenance,
    WorkflowBuildPlan,
    WorkflowDefinition,
    WorkflowRegistrationProposal,
    WorkflowResolution,
    WorkflowValidation,
)
from services.core import package_files

from .validation import validate_workflow

ModelT = TypeVar("ModelT", bound=BaseModel)

_REQUIRED_FILES = (
    "workflow.json",
    "evaluation/eval.json",
    "provenance/resolution.json",
    "provenance/build-plan.json",
    "provenance/research-decisions.json",
    "README.md",
)


class WorkflowPackageValidator:
    def __init__(self, repository_root: str | Path = ".") -> None:
        self.repository_root = Path(repository_root).resolve()

    def validate(self, package_root: str | Path) -> WorkflowValidation:
        root = Path(package_root).resolve()
        errors: list[str] = []
        checks = {"fixed_shell_complete": all((root / item).is_file() for item in _REQUIRED_FILES)}
        if not checks["fixed_shell_complete"]:
            errors.append("fixed workflow shell is incomplete")
        workflow = self._load_json(root / "workflow.json", WorkflowDefinition, errors)
        plan = self._load_json(root / "provenance/build-plan.json", WorkflowBuildPlan, errors)
        resolution = self._load_json(
            root / "provenance/resolution.json", WorkflowResolution, errors
        )
        checks["workflow_valid"] = workflow is not None
        checks["build_plan_valid"] = plan is not None
        checks["resolution_attached"] = bool(
            plan and resolution and plan.resolution.resolution_id == resolution.resolution_id
        )
        checks["workflow_matches_plan"] = bool(
            workflow and plan and workflow.workflow_id == plan.workflow.workflow_id
        )
        if workflow is not None:
            try:
                validate_workflow(
                    workflow,
                    skills={
                        p.name
                        for p in (self.repository_root / ".opencode/skills").iterdir()
                        if p.is_dir()
                    },
                    capabilities={
                        p.stem for p in (self.repository_root / "system/capabilities").glob("*.md")
                    },
                    prompts={
                        (p.parent.name, p.stem)
                        for p in (self.repository_root / "system/workflow_prompts").glob("*/*.json")
                    },
                    rubrics={
                        (p.parent.name, p.stem)
                        for p in (self.repository_root / "system/reasoning_rubrics").glob(
                            "*/*.json"
                        )
                    },
                    profiles={
                        (p.parent.name, p.stem)
                        for p in (self.repository_root / "system/agent_profiles").glob("*/*.json")
                    },
                )
                checks["graph_and_bindings_valid"] = True
            except Exception as exc:
                checks["graph_and_bindings_valid"] = False
                errors.append(str(exc))
        else:
            checks["graph_and_bindings_valid"] = False
        test_refs = sorted(str(path.relative_to(root)) for path in root.glob("tests/**/test_*.py"))
        checks["tests_present"] = bool(test_refs)
        if not test_refs:
            errors.append("no executable workflow tests found")
        evaluation_refs: list[str] = []
        evaluation_path = root / "evaluation/eval.json"
        try:
            evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
            checks["evaluation_cases_present"] = bool(
                isinstance(evaluation, dict) and evaluation.get("cases")
            )
        except Exception as exc:
            checks["evaluation_cases_present"] = False
            errors.append(f"invalid eval.json: {exc}")
        if checks["evaluation_cases_present"]:
            evaluation_refs.append(str(evaluation_path.relative_to(root)))
        else:
            errors.append("workflow evaluation has no cases")
        if plan and plan.research_questions:
            try:
                research = json.loads(
                    (root / "provenance/research-decisions.json").read_text(encoding="utf-8")
                )
                checks["research_gaps_resolved"] = bool(research.get("decisions"))
            except Exception as exc:
                checks["research_gaps_resolved"] = False
                errors.append(f"invalid research decisions: {exc}")
        else:
            checks["research_gaps_resolved"] = True
        package_hash = hash_workflow_package(root) if root.exists() else "sha256:missing"
        return WorkflowValidation(
            validation_id=f"workflow-validation-{uuid4().hex}",
            build_id=plan.build_id if plan else "unknown",
            workflow_id=workflow.workflow_id if workflow else root.name,
            package_hash=package_hash,
            checks=checks,
            test_refs=test_refs,
            evaluation_refs=evaluation_refs,
            errors=errors,
            created_at=datetime.now(UTC),
            provenance=Provenance(source_path=str(root), content_hash=package_hash),
        )

    @staticmethod
    def _load_json(path: Path, contract: type[ModelT], errors: list[str]) -> ModelT | None:
        try:
            return contract.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            errors.append(f"invalid {path.name}: {exc}")
            return None


class WorkflowRegistrar:
    """Create a hash-bound proposal; installation remains a separate review action."""

    def propose(
        self,
        package_root: str | Path,
        plan: WorkflowBuildPlan,
        validation: WorkflowValidation,
    ) -> WorkflowRegistrationProposal:
        root = Path(package_root).resolve()
        if not validation.passed:
            raise ValueError("workflow validation must pass before registration proposal")
        if validation.build_id != plan.build_id or validation.package_hash != hash_workflow_package(
            root
        ):
            raise ValueError("validation does not match the current workflow package")
        proposal = WorkflowRegistrationProposal(
            proposal_id=f"workflow-registration-{uuid4().hex}",
            build_id=plan.build_id,
            workflow_id=plan.workflow.workflow_id,
            workflow_version=plan.workflow.version,
            package_path=str(root),
            package_hash=validation.package_hash,
            resolution_ref="provenance/resolution.json",
            validation_ref="provenance/validation.json",
            registration_scope=plan.registration_scope,
            created_at=datetime.now(UTC),
            provenance=Provenance(
                source_records=[plan.resolution.resolution_id, validation.validation_id],
                content_hash=validation.package_hash,
            ),
        )
        (root / "provenance/validation.json").write_text(
            json.dumps(validation.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (root / "provenance/registration-proposal.json").write_text(
            json.dumps(proposal.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return proposal


def hash_workflow_package(root: str | Path) -> str:
    digest = hashlib.sha256()
    for relative, path in package_files(root):
        if path.name in {"validation.json", "registration-proposal.json"}:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"
