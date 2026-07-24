"""Authoritative, persisted MVP dataset diagnostic workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from lasi.contracts import (
    ApprovalRecord,
    DatasetManifest,
    DecisionRecord,
    ExperimentPlan,
    KnowledgeProposal,
    ProjectConfig,
    StaticReportData,
    ToolRunResult,
)
from lasi.contracts import (
    DatasetCharacterization as DatasetCharacterizationContract,
)
from lasi.contracts import (
    ScientistReview as ScientistReviewContract,
)
from lasi.contracts.models import ArtifactRecord, Provenance, ReportSection
from lasi.core.artifacts import ArtifactStore
from lasi.datasets import characterize_dataset, create_dataset_version, validate_dataset
from lasi.decisions import DecisionContext, DecisionGate, Recommendation
from lasi.experiments import assemble_diagnostic_packet, compile_plan, require_allowed_decision
from lasi.knowledge.proposals import KnowledgeCurator
from lasi.memory import (
    Approval,
    Artifact,
    Dataset,
    DatasetCharacterization,
    DatasetVersion,
    Decision,
    KnowledgeRegistration,
    OperationalMemory,
    Project,
    Report,
    ScientistReview,
    ToolRun,
)
from lasi.memory import (
    ExperimentPlan as ExperimentPlanRecord,
)
from lasi.outcomes import OutcomeService
from lasi.providers import MockScientistProvider
from lasi.reports import ReportRenderer
from lasi.tools import LocalToolRunner, ToolRegistry


@dataclass(frozen=True, slots=True)
class DiagnosticWorkflowRequest:
    """Inputs for one complete, local MVP diagnostic run."""

    project: ProjectConfig
    manifest: DatasetManifest
    dataset_root: Path
    dataset_approval: ApprovalRecord
    tool_registry: ToolRegistry
    provider: MockScientistProvider
    artifact_store: ArtifactStore
    report_path: Path
    knowledge_path: Path
    created_by: str = "lasi-workflow"
    tool_id: str = "baseline"


@dataclass(frozen=True, slots=True)
class DiagnosticWorkflowResult:
    """All durable and produced records from one diagnostic run."""

    dataset_version_id: str
    characterization_id: str
    experiment_plan_id: str
    decision_id: str
    tool_run_id: str
    diagnostic_packet_id: str
    scientist_review_id: str
    post_review_decision_id: str
    report_id: str
    outcome_event_id: str
    knowledge_proposal_id: str
    report_path: Path


def run_diagnostic_workflow(
    request: DiagnosticWorkflowRequest, memory: OperationalMemory
) -> DiagnosticWorkflowResult:
    """Run the MVP diagnostic path and persist every handoff.

    The function is intentionally the only coordinator for this vertical slice:
    component services still own validation, authorization, execution, artifacts,
    reporting, outcomes, and knowledge semantics respectively.
    """

    _ensure_project_and_dataset(request, memory)
    _persist_approval(request.dataset_approval, request.project.project_id, memory)
    version = create_dataset_version(
        request.manifest,
        manifest_path=request.manifest.provenance.source_path or "manifest.parquet",
        created_by=request.created_by,
        approval=request.dataset_approval,
    )
    memory.add(
        DatasetVersion(
            dataset_version_id=version.dataset_version_id,
            dataset_id=version.dataset_id,
            project_id=request.project.project_id,
            version=version.version,
            data_hash=version.data_hash,
            status=version.status,
            benchmark=version.benchmark,
            payload=version.model_dump(mode="json"),
        )
    )

    validation = validate_dataset(request.manifest, request.dataset_root)
    if not validation.valid:
        raise ValueError("dataset validation failed: " + "; ".join(validation.errors))
    characterization = characterize_dataset(
        request.manifest,
        request.dataset_root,
        characterization_id=f"characterization-{version.dataset_version_id}",
    )
    _persist_characterization(characterization, memory)

    plan_result = compile_plan(
        {
            "project_id": request.project.project_id,
            "dataset_version": version.dataset_version_id,
            "hypothesis": "A bounded baseline establishes the evidence floor.",
            "experiment_type": "baseline_probe",
            "planned_tool_runs": [{"tool_id": request.tool_id}],
            "expected_artifacts": ["tool-result.json"],
            "budget_estimate": {"cpu_hours": 1},
            "created_by": request.created_by,
        },
        tool_registry=request.tool_registry.all(),
    )
    plan = plan_result.plan
    _persist_plan(plan, memory)

    decision = DecisionGate().evaluate(
        Recommendation(
            recommendation_id=f"recommendation-{plan.experiment_plan_id}",
            project_id=request.project.project_id,
            action="run_local_experiment",
        ),
        context=DecisionContext(
            dataset_status="validated",
            available_tools=request.tool_registry.all(),
            now=datetime.now(UTC),
        ),
        plan=plan,
    )
    _require_allowed(decision, plan)
    _persist_decision(decision, memory)

    tool_result = LocalToolRunner(request.tool_registry).run(
        request.tool_id,
        request.project.project_id,
        version.dataset_version_id,
        plan=plan,
        decision=decision,
        input_refs=[version.manifest_path],
        experiment_plan_id=plan.experiment_plan_id,
    )
    _persist_tool_run(tool_result, memory)
    artifact = _persist_tool_artifact(tool_result, request, plan, decision, memory)

    packet = assemble_diagnostic_packet(
        diagnostic_packet_id=f"packet-{plan.experiment_plan_id}",
        project_id=request.project.project_id,
        problem_type=request.project.problem_type,
        dataset_version_id=version.dataset_version_id,
        privacy_mode=request.project.privacy_mode,
        dataset_characterization_summary=(
            characterization.quality_profile.summary or "Dataset characterized."
        ),
        evaluation_policy=request.project.evaluation_policy,
        tool_results=[tool_result],
        allowed_recommendation_types=["run_error_analysis", "stop_low_expected_value"],
        artifact_refs=[artifact.artifact_uri],
    )
    review = request.provider.review(packet, experiment_ids=[plan.experiment_plan_id])
    _persist_review(review, memory)

    post_plan = _compile_post_review_plan(request, version.dataset_version_id, review)
    post_decision = _post_review_decision(request, post_plan)
    _persist_plan(post_plan, memory)
    _persist_decision(post_decision, memory)

    report = _report_data(
        request, version.dataset_version_id, characterization, plan, decision, review
    )
    report_path = ReportRenderer().write_immutable(report, request.report_path)
    memory.add(
        Report(
            report_id=report.report_id,
            project_id=request.project.project_id,
            report_state="immutable",
            payload=report.model_dump(mode="json"),
        )
    )
    report_artifact = _log_report_artifact(report_path, request, plan, report.report_id, memory)
    with memory.transaction() as session:
        persisted_report = session.get(Report, report.report_id)
        if persisted_report is None:
            raise RuntimeError("report record disappeared before artifact linking")
        persisted_report.artifact_id = report_artifact.artifact_id

    outcome_event = OutcomeService(memory).transition(
        request.project.project_id,
        "validated_not_deployed",
        reason="MVP diagnostic completed; no deployment was authorized.",
        owner=request.created_by,
        evidence=[report_artifact.artifact_uri, artifact.artifact_uri],
        related_report_id=report.report_id,
        related_experiment_id=plan.experiment_plan_id,
    )
    proposal = _knowledge_proposal(request, review, outcome_event.event_id)
    proposal = KnowledgeCurator().propose(proposal)
    _persist_knowledge_proposal(proposal, request, memory)

    return DiagnosticWorkflowResult(
        dataset_version_id=version.dataset_version_id,
        characterization_id=characterization.characterization_id,
        experiment_plan_id=plan.experiment_plan_id,
        decision_id=decision.decision_id,
        tool_run_id=tool_result.tool_run_id,
        diagnostic_packet_id=packet.diagnostic_packet_id,
        scientist_review_id=review.review_id,
        post_review_decision_id=post_decision.decision_id,
        report_id=report.report_id,
        outcome_event_id=outcome_event.event_id,
        knowledge_proposal_id=proposal.proposal_id,
        report_path=report_path,
    )


def _ensure_project_and_dataset(
    request: DiagnosticWorkflowRequest, memory: OperationalMemory
) -> None:
    if not memory.project_exists(request.project.project_id):
        memory.add(
            Project(
                project_id=request.project.project_id,
                project_name=request.project.project_name,
                problem_type=request.project.problem_type,
                modality=request.project.modality,
                payload=request.project.model_dump(mode="json"),
            )
        )
    if memory.get(Dataset, request.manifest.dataset_id) is None:
        memory.add(
            Dataset(
                dataset_id=request.manifest.dataset_id,
                project_id=request.project.project_id,
                name=request.manifest.dataset_id,
                payload=request.manifest.model_dump(mode="json"),
            )
        )


def _persist_approval(approval: ApprovalRecord, project_id: str, memory: OperationalMemory) -> None:
    if approval.approval_status != "approved":
        raise PermissionError("dataset workflow requires an approved durable approval")
    if approval.project_id != project_id:
        raise PermissionError("dataset workflow approval belongs to a different project")
    if approval.action_type != "create_dataset_version":
        raise PermissionError("dataset workflow approval must authorize dataset version creation")
    if memory.get(Approval, approval.approval_id) is None:
        memory.add(
            Approval(
                approval_id=approval.approval_id,
                project_id=approval.project_id,
                action_type=approval.action_type,
                approval_status=approval.approval_status,
                approved_by=approval.approved_by,
                expires_at=approval.expires_at,
                payload=approval.model_dump(mode="json"),
            )
        )


def _persist_characterization(
    characterization: DatasetCharacterizationContract, memory: OperationalMemory
) -> None:
    memory.add(
        DatasetCharacterization(
            characterization_id=characterization.characterization_id,
            project_id=characterization.project_id,
            dataset_version_id=characterization.dataset_version_id,
            sample_size=characterization.sample_size,
            status=characterization.status,
            payload=characterization.model_dump(mode="json"),
        )
    )


def _persist_plan(plan: ExperimentPlan, memory: OperationalMemory) -> None:
    if memory.get(ExperimentPlanRecord, plan.experiment_plan_id) is None:
        memory.add(
            ExperimentPlanRecord(
                experiment_plan_id=plan.experiment_plan_id,
                project_id=plan.project_id,
                dataset_version_id=plan.dataset_version,
                execution_backend=plan.execution_backend,
                approval_required=plan.approval_required,
                payload=plan.model_dump(mode="json"),
            )
        )


def _persist_decision(decision: DecisionRecord, memory: OperationalMemory) -> None:
    if memory.get(Decision, decision.decision_id) is None:
        memory.add(
            Decision(
                decision_id=decision.decision_id,
                project_id=decision.project_id,
                experiment_plan_id=decision.experiment_plan_id,
                decision=decision.decision,
                allowed=decision.allowed,
                approval_required=decision.approval_required,
                payload=decision.model_dump(mode="json"),
            )
        )


def _require_allowed(decision: DecisionRecord, plan: ExperimentPlan) -> None:
    if not decision.allowed:
        raise PermissionError(f"experiment decision was not allowed: {decision.decision}")
    require_allowed_decision(plan, decision)


def _persist_tool_run(result: ToolRunResult, memory: OperationalMemory) -> None:
    memory.add(
        ToolRun(
            tool_run_id=result.tool_run_id,
            project_id=result.project_id,
            experiment_plan_id=result.experiment_plan_id,
            dataset_version_id=result.dataset_version_id,
            tool_id=result.tool_id,
            tool_version=result.tool_version,
            status=result.status,
            execution_backend=result.execution_backend,
            start_time=result.start_time,
            end_time=result.end_time,
            payload=result.model_dump(mode="json"),
        )
    )


def _persist_tool_artifact(
    result: ToolRunResult,
    request: DiagnosticWorkflowRequest,
    plan: ExperimentPlan,
    decision: DecisionRecord,
    memory: OperationalMemory,
) -> ArtifactRecord:
    with request.artifact_store.start_run(
        f"tool-{result.tool_run_id}",
        tags={"project_id": request.project.project_id, "tool_run_id": result.tool_run_id},
    ) as artifact_run:
        record = request.artifact_store.log_json(
            artifact_run,
            result.model_dump(mode="json"),
            filename=f"tool-runs/{result.tool_run_id}.json",
            artifact_type="tool_run_result",
            project_id=request.project.project_id,
            dataset_version_id=result.dataset_version_id,
            experiment_id=plan.experiment_plan_id,
            tool_run_id=result.tool_run_id,
            decision_id=decision.decision_id,
        )
    memory.add(
        Artifact(
            artifact_id=record.artifact_id,
            artifact_uri=record.artifact_uri,
            artifact_type=record.artifact_type,
            project_id=record.project_id,
            dataset_version_id=record.dataset_version_id,
            tool_run_id=record.tool_run_id,
            decision_id=record.decision_id,
            immutable=True,
            payload=record.model_dump(mode="json"),
        )
    )
    return record


def _persist_review(review: ScientistReviewContract, memory: OperationalMemory) -> None:
    memory.add(
        ScientistReview(
            review_id=review.review_id,
            project_id=review.project_id,
            provider_profile_id=review.provider_profile_id,
            diagnostic_packet_id=review.diagnostic_packet_id,
            primary_diagnosis=review.primary_diagnosis,
            diagnosis_confidence=review.diagnosis_confidence,
            payload=review.model_dump(mode="json"),
        )
    )


def _compile_post_review_plan(
    request: DiagnosticWorkflowRequest, dataset_version_id: str, review: ScientistReviewContract
) -> ExperimentPlan:
    action = review.recommended_next_action
    if action == "run_error_analysis":
        experiment_type = "error_analysis"
        tool_id = "error_analysis"
    else:
        experiment_type = "static_report_generation"
        tool_id = "static_report"
    return compile_plan(
        {
            "project_id": request.project.project_id,
            "dataset_version": dataset_version_id,
            "hypothesis": f"Post-review action: {action}",
            "experiment_type": experiment_type,
            "planned_tool_runs": [{"tool_id": tool_id}],
            "created_by": request.created_by,
        },
        tool_registry=request.tool_registry.all(),
    ).plan


def _post_review_decision(
    request: DiagnosticWorkflowRequest, plan: ExperimentPlan
) -> DecisionRecord:
    return DecisionGate().evaluate(
        Recommendation(
            recommendation_id=f"post-review-{plan.experiment_plan_id}",
            project_id=request.project.project_id,
            action="run_local_experiment",
        ),
        context=DecisionContext(
            dataset_status="validated",
            available_tools=request.tool_registry.all(),
        ),
        plan=plan,
    )


def _report_data(
    request: DiagnosticWorkflowRequest,
    dataset_version_id: str,
    characterization: DatasetCharacterizationContract,
    plan: ExperimentPlan,
    decision: DecisionRecord,
    review: ScientistReviewContract,
) -> StaticReportData:
    def section(summary: str, **content: Any) -> ReportSection:
        return ReportSection(section_status="complete", summary=summary, content=content)

    empty = ReportSection(section_status="not_run", summary="Not run in this MVP phase.")
    return StaticReportData(
        report_id=f"report-{plan.experiment_plan_id}",
        report_header={
            "project_id": request.project.project_id,
            "dataset_version_id": dataset_version_id,
            "title": f"LASI diagnostic report: {request.project.project_name}",
        },
        executive_summary=section("Diagnostic workflow completed."),
        current_decision=section("Post-review authorization is recorded separately."),
        dataset_summary=section(
            "Dataset version validated.", dataset_version_id=dataset_version_id
        ),
        dataset_characterization=section(
            "Dataset characterized.", characterization_id=characterization.characterization_id
        ),
        experiment_summary=section(
            "Approved baseline tool run completed.", plan_id=plan.experiment_plan_id
        ),
        model_comparison=empty,
        performance_gap_diagnosis=section(
            review.primary_diagnosis, confidence=review.diagnosis_confidence
        ),
        learning_curves=empty,
        error_analysis=empty,
        cluster_or_latent_analysis=empty,
        scientist_review=section("Provider recommendation recorded.", review_id=review.review_id),
        decision_record=section(
            "Experiment decision recorded.",
            decision_id=decision.decision_id,
            allowed=decision.allowed,
        ),
        knowledge_context=empty,
        recommendation=section(review.recommended_next_action, recommendation_only=True),
        project_outcome=section("Validated, not deployed."),
        appendix=section("Provenance is recorded in SQLite and MLflow artifacts."),
        project_outcome_status="validated_not_deployed",
        provenance=Provenance(
            author=request.created_by,
            created_at=datetime.now(UTC),
            source_records=[plan.experiment_plan_id, decision.decision_id, review.review_id],
        ),
    )


def _log_report_artifact(
    report_path: Path,
    request: DiagnosticWorkflowRequest,
    plan: ExperimentPlan,
    report_id: str,
    memory: OperationalMemory,
) -> ArtifactRecord:
    with request.artifact_store.start_run(f"report-{plan.experiment_plan_id}") as artifact_run:
        record = request.artifact_store.log_file(
            artifact_run,
            report_path,
            artifact_type="static_report",
            artifact_path=f"reports/{report_path.name}",
            project_id=request.project.project_id,
            experiment_id=plan.experiment_plan_id,
            report_id=report_id,
        )
    memory.add(
        Artifact(
            artifact_id=record.artifact_id,
            artifact_uri=record.artifact_uri,
            artifact_type=record.artifact_type,
            project_id=record.project_id,
            report_id=record.report_id,
            immutable=True,
            payload=record.model_dump(mode="json"),
        )
    )
    return record


def _knowledge_proposal(
    request: DiagnosticWorkflowRequest,
    review: ScientistReviewContract,
    outcome_event_id: str,
) -> KnowledgeProposal:
    return KnowledgeProposal(
        proposal_id=f"proposal-{review.review_id}",
        proposal_type="lesson",
        project_id=request.project.project_id,
        source=review.review_id,
        title="Diagnostic workflow lesson candidate",
        summary=review.primary_diagnosis,
        evidence_references=[review.review_id, outcome_event_id],
        rationale="Drafted from the completed diagnostic evidence; human review remains required.",
        expected_value=review.expected_value,
        impact="future_diagnostic_guidance",
        risk="single_project_observation",
        recommended_approvers=["research-owner"],
        status="draft",
    )


def _persist_knowledge_proposal(
    proposal: KnowledgeProposal, request: DiagnosticWorkflowRequest, memory: OperationalMemory
) -> None:
    request.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "document_id": proposal.proposal_id,
        "type": "lesson",
        "status": "draft",
        "owner": request.created_by,
        "created_at": date.today().isoformat(),
        "source_projects": [request.project.project_id],
        "evidence_level": "single_project_observation",
    }
    body = "\n".join(
        [
            "---",
            *[f"{key}: {json.dumps(value)}" for key, value in frontmatter.items()],
            "---",
            "",
            f"# {proposal.title}",
            "",
            proposal.summary,
            "",
            f"Evidence references: {', '.join(proposal.evidence_references)}",
            "",
        ]
    )
    request.knowledge_path.write_text(body, encoding="utf-8", newline="\n")
    memory.add(
        KnowledgeRegistration(
            document_id=proposal.proposal_id,
            project_id=request.project.project_id,
            document_type=proposal.proposal_type,
            status=proposal.status,
            owner=request.created_by,
            path=str(request.knowledge_path),
            payload=proposal.model_dump(mode="json"),
        )
    )
