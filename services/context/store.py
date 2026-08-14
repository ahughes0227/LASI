"""Durable filesystem operations for system and project ICM."""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path, PurePosixPath

import yaml  # type: ignore[import-untyped]

from services.contracts import ProjectConfig

from .models import (
    ArtifactContract,
    EvidenceClaim,
    EvidenceStatus,
    ExperimentContext,
    ICMProject,
    ProjectState,
)

_PROJECT_DIRS = (
    "00_task",
    "10_context",
    "20_work/exploration",
    "20_work/research",
    "20_work/features",
    "20_work/experiments",
    "20_work/interpretation",
    "30_evidence/claims",
    "30_evidence/metrics",
    "30_evidence/plots",
    "30_evidence/comparisons",
    "30_evidence/failures",
    "30_evidence/promotions",
    "40_output",
)


class ICMStore:
    """Own regenerable context projections without becoming workflow authority."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.system_root = self.root / "system"
        self.projects_root = self.root / "projects"

    def initialize_system(self) -> None:
        files = {
            "constitution.md": "# LASI System Constitution\n\nEvidence first. Recommendations are not commands.\n",
            "policies/evidence.md": "# Evidence Policy\n\nClaims must link to durable evidence.\n",
            "policies/validation.md": "# Validation Policy\n\nValidation must match the project evaluation policy.\n",
            "policies/escalation.md": "# Escalation Policy\n\nEscalate high-consequence or ambiguous actions.\n",
            "policies/safety.md": "# Safety Policy\n\nRespect privacy, authorization, and execution boundaries.\n",
            "policies/memory_promotion.md": "# Memory Promotion Policy\n\nPromotion is explicit, evidence-backed, and reviewed.\n",
            "organizational_rules/contracts.md": "# Agent Contracts\n\nWorkers read declared inputs and write declared artifacts.\n",
            "organizational_rules/review.md": "# Review\n\nCritics inspect evidence and durable artifacts.\n",
            "organizational_rules/delegation.md": "# Delegation\n\nLASI decides who does what; ICM supplies context.\n",
            "capabilities/README.md": "# Capabilities\n\nCapabilities define bounded work and artifact contracts.\n",
            "capabilities/eda.md": "# EDA Capability\n\nAnalyze schema, quality, distributions, and leakage.\n",
            "capabilities/research.md": "# Research Capability\n\nRetrieve and summarize source-backed context.\n",
            "capabilities/feature_engineering.md": "# Feature Engineering Capability\n\nPreserve comparability and provenance.\n",
            "capabilities/modeling.md": "# Modeling Capability\n\nExecute only approved experiment plans.\n",
            "capabilities/evaluation.md": "# Evaluation Capability\n\nInspect metrics and validation evidence.\n",
            "capabilities/critique.md": "# Critique Capability\n\nInvalidate unsupported claims and affected experiments.\n",
            "models/registry.yaml": "models: []\n",
            "models/routing_rules.md": "# Model Routing Rules\n\nRouting is governed by provider and decision layers.\n",
            "playbooks/README.md": "# Playbooks\n\nPlaybooks are retrieved selectively.\n",
            "playbooks/tabular_classification.md": "# Tabular Classification\n\nValidate and characterize before modeling.\n",
            "playbooks/time_series.md": "# Time Series\n\nCheck temporal leakage before validation.\n",
            "playbooks/vision.md": "# Vision\n\nReview labels and coverage before scaling.\n",
            "playbooks/anomaly_detection.md": "# Anomaly Detection\n\nDocument anomaly and validation assumptions.\n",
            "learned_principles/README.md": "# Learned Principles\n\nOnly reviewed, reusable lessons belong here.\n",
        }
        for relative, content in files.items():
            self._write_text(self.system_root, relative, content, overwrite=False)

    def initialize_project(self, config: ProjectConfig, *, overwrite: bool = False) -> ICMProject:
        root = self._project_root(config.project_id)
        for directory in _PROJECT_DIRS:
            (root / directory).mkdir(parents=True, exist_ok=True)
        self._write_text(
            root, "00_task/objective.md", f"# Objective\n\n{config.project_name}\n", overwrite
        )
        self._write_text(
            root,
            "00_task/success_criteria.md",
            "# Success Criteria\n\nDefine measurable success criteria.\n",
            overwrite,
        )
        self._write_text(
            root,
            "00_task/constraints.md",
            f"# Constraints\n\nPrivacy mode: {config.privacy_mode}\n",
            overwrite,
        )
        self._write_text(
            root,
            "10_context/current_state.md",
            "# Current State\n\nProject initialized.\n",
            overwrite,
        )
        self._write_text(
            root,
            "10_context/domain_context.md",
            "# Domain Context\n\nNot available yet.\n",
            overwrite,
        )
        self._write_text(
            root,
            "10_context/prior_findings.md",
            "# Prior Findings\n\nNo project findings have been recorded.\n",
            overwrite,
        )
        self._write_text(
            root,
            "40_output/limitations.md",
            "# Limitations\n\nNot assessed yet.\n",
            overwrite,
        )
        return ICMProject(
            project_id=config.project_id, root=str(root), directories=list(_PROJECT_DIRS)
        )

    def write_artifact(
        self,
        project_id: str,
        relative: str,
        content: str,
        *,
        overwrite: bool = False,
        contract: ArtifactContract | None = None,
    ) -> Path:
        if contract is not None and relative not in contract.writes:
            raise PermissionError(f"artifact is not declared in contract writes: {relative}")
        path = self._safe_project_path(project_id, relative)
        if path.exists() and not overwrite:
            raise FileExistsError(f"ICM artifact already exists: {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_artifact(self, project_id: str, relative: str) -> str:
        return self._safe_project_path(project_id, relative).read_text(encoding="utf-8")

    def validate_contract(self, project_id: str, contract: ArtifactContract) -> None:
        for relative in contract.reads:
            if not self._safe_project_path(project_id, relative).exists():
                raise FileNotFoundError(f"declared input is missing: {relative}")

    def initialize_experiment(
        self,
        project_id: str,
        experiment_id: str,
        *,
        hypothesis: str,
        config: dict[str, object],
        inputs: list[str],
        contract: ArtifactContract | None = None,
    ) -> ExperimentContext:
        root = f"20_work/experiments/{experiment_id}"
        self._safe_project_path(project_id, f"{root}/artifacts").mkdir(parents=True, exist_ok=True)
        self.write_artifact(
            project_id,
            f"{root}/hypothesis.md",
            f"# Hypothesis\n\n{hypothesis}\n",
            contract=contract,
        )
        self.write_artifact(
            project_id,
            f"{root}/config.yaml",
            yaml.safe_dump(config, sort_keys=True),
            contract=contract,
        )
        self.write_artifact(
            project_id,
            f"{root}/inputs.md",
            "# Inputs\n\n" + "\n".join(f"- {item}" for item in inputs) + "\n",
            contract=contract,
        )
        return ExperimentContext(
            project_id=project_id,
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            inputs=inputs,
        )

    def record_experiment_result(
        self,
        project_id: str,
        experiment_id: str,
        *,
        status: str,
        result: str,
        artifact_refs: list[str] | None = None,
        contract: ArtifactContract | None = None,
    ) -> Path:
        root = f"20_work/experiments/{experiment_id}"
        return self.write_artifact(
            project_id,
            f"{root}/results.md",
            "# Experiment Results\n\n"
            f"Status: {status}\n\n{result}\n\nArtifacts: {artifact_refs or []}\n",
            contract=contract,
        )

    def record_critique(
        self,
        project_id: str,
        experiment_id: str,
        critique: str,
        *,
        contract: ArtifactContract | None = None,
    ) -> Path:
        return self.write_artifact(
            project_id,
            f"20_work/experiments/{experiment_id}/critique.md",
            f"# Critique\n\n{critique}\n",
            contract=contract,
        )

    def write_claim(self, claim: EvidenceClaim) -> Path:
        path = self._safe_project_path(
            claim.project_id, f"30_evidence/claims/{claim.claim_id}.yaml"
        )
        if path.exists():
            raise FileExistsError(f"claim already exists: {claim.claim_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(claim.model_dump(mode="json", by_alias=True), sort_keys=False),
            encoding="utf-8",
        )
        return path

    def invalidate_claim(self, project_id: str, claim_id: str, reason: str) -> EvidenceClaim:
        path = self._safe_project_path(project_id, f"30_evidence/claims/{claim_id}.yaml")
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        claim = EvidenceClaim.model_validate(value)
        claim.status = EvidenceStatus.INVALIDATED
        claim.invalidated_by.append(reason)
        path.write_text(
            yaml.safe_dump(claim.model_dump(mode="json", by_alias=True), sort_keys=False),
            encoding="utf-8",
        )
        failure = self._safe_project_path(project_id, f"30_evidence/failures/{claim_id}.md")
        failure.write_text(f"# Invalidated claim\n\n{reason}\n", encoding="utf-8")
        for experiment_id in claim.experiment_ids:
            self._mark_experiment_invalid(project_id, experiment_id, reason)
        for dependent in self._claims(project_id):
            if (
                claim_id in dependent.depends_on_claim_ids
                and dependent.status != EvidenceStatus.INVALIDATED
            ):
                self.invalidate_claim(
                    project_id, dependent.claim_id, f"depends on invalidated claim {claim_id}"
                )
        current_state = self._safe_project_path(project_id, "10_context/current_state.md")
        existing_state = self._read_optional(current_state) or "# Current State\n\n"
        update = f"- Claim {claim_id} invalidated: {reason}\n"
        if update not in existing_state:
            current_state.write_text(existing_state + update, encoding="utf-8")
        return claim

    def reconstruct_project_state(self, project_id: str) -> ProjectState:
        """Read the human-facing projection; callers must not use it to schedule tasks."""
        root = self._project_root(project_id)
        experiments: list[ExperimentContext] = []
        for experiment_root in sorted((root / "20_work/experiments").glob("*")):
            if not experiment_root.is_dir():
                continue
            hypothesis = self._read_optional(experiment_root / "hypothesis.md") or ""
            inputs = self._bullet_values(self._read_optional(experiment_root / "inputs.md") or "")
            result = self._read_optional(experiment_root / "results.md") or ""
            invalidated = self._read_optional(experiment_root / "invalidated.md") or ""
            status = "invalidated" if invalidated else self._result_status(result)
            experiments.append(
                ExperimentContext(
                    project_id=project_id,
                    experiment_id=experiment_root.name,
                    hypothesis=hypothesis.removeprefix("# Hypothesis\n\n").strip(),
                    status=status,
                    inputs=inputs,
                    invalidation_reasons=[invalidated] if invalidated else [],
                )
            )
        failures = [path.name for path in sorted((root / "30_evidence/failures").glob("*.md"))]
        return ProjectState(
            project_id=project_id,
            objective=self._read_optional(root / "00_task/objective.md"),
            constraints=self._read_optional(root / "00_task/constraints.md"),
            current_state=self._read_optional(root / "10_context/current_state.md"),
            experiments=experiments,
            claims=self._claims(project_id),
            failures=failures,
            recommendation=self._read_optional(root / "40_output/recommendation.md"),
        )

    def _safe_project_path(self, project_id: str, relative: str) -> Path:
        return self._safe_path(self._project_root(project_id), relative)

    def project_root(self, project_id: str) -> Path:
        if Path(project_id).name != project_id or project_id in {"", ".", ".."}:
            raise ValueError(f"project_id must be a single safe path component: {project_id}")
        return self.projects_root / project_id

    def _project_root(self, project_id: str) -> Path:
        return self.project_root(project_id)

    def _claims(self, project_id: str) -> list[EvidenceClaim]:
        claims_root = self._project_root(project_id) / "30_evidence/claims"
        if not claims_root.exists():
            return []
        return [
            EvidenceClaim.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            for path in sorted(claims_root.glob("*.yaml"))
        ]

    def _mark_experiment_invalid(self, project_id: str, experiment_id: str, reason: str) -> None:
        path = self._safe_project_path(
            project_id, f"20_work/experiments/{experiment_id}/invalidated.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_optional(path) or "# Invalidated\n\n"
        if reason not in existing:
            path.write_text(f"{existing}- {reason}\n", encoding="utf-8")

    @staticmethod
    def _read_optional(path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.is_file() else None

    @staticmethod
    def _bullet_values(content: str) -> list[str]:
        return [line[2:] for line in content.splitlines() if line.startswith("- ")]

    @staticmethod
    def _result_status(content: str) -> str:
        for line in content.splitlines():
            if line.startswith("Status: "):
                return line.removeprefix("Status: ").strip()
        return "planned"

    @staticmethod
    def _safe_path(root: Path, relative: str) -> Path:
        parsed = PurePosixPath(relative)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise ValueError(f"path escapes ICM root: {relative}")
        path = (root / Path(*parsed.parts)).resolve()
        if root.resolve() not in path.parents and path != root.resolve():
            raise ValueError(f"path escapes ICM root: {relative}")
        return path

    @staticmethod
    def _write_text(root: Path, relative: str, content: str, overwrite: bool) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")
