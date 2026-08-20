"""Authoritative, persisted dataset diagnostic workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from services.context import (
    ArtifactContract,
    ContextRequest,
    ContextResolver,
    EvidenceClaim,
    EvidenceItem,
    EvidenceStatus,
    ICMStore,
    OperationalMemoryRetriever,
)
from services.contracts import (
    ApprovalRecord,
    DatasetManifest,
    DecisionRecord,
    ExperimentPlan,
    KnowledgeProposal,
    ProjectConfig,
    StaticReportData,
    TokenUsageReport,
    ToolRunResult,
)
from services.contracts import (
    DatasetCharacterization as DatasetCharacterizationContract,
)
from services.contracts import (
    ScientistReview as ScientistReviewContract,
)
from services.contracts.models import ArtifactRecord, Provenance, ReportSection
from services.core.artifacts import ArtifactStore
from services.datasets import characterize_dataset, create_dataset_version, validate_dataset
from services.decisions import DecisionContext, DecisionGate, Recommendation
from services.experiments import assemble_diagnostic_packet, compile_plan, require_allowed_decision
from services.knowledge.proposals import KnowledgeCurator
from services.memory import (
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
from services.memory import (
    ExperimentPlan as ExperimentPlanRecord,
)
from services.outcomes import OutcomeService
from services.providers import MockScientistProvider
from services.reports import ReportRenderer
from services.telemetry import TokenUsageService
from services.tools import LocalToolRunner, ToolRegistry


@dataclass(frozen=True, slots=True)
class DiagnosticWorkflowRequest:
    """Inputs for one complete local diagnostic run."""

    project: ProjectConfig
    manifest: DatasetManifest
    dataset_root: Path
    dataset_approval: ApprovalRecord
    tool_registry: ToolRegistry
    provider: MockScientistProvider
    artifact_store: ArtifactStore
    report_path: Path
    knowledge_path: Path
    icm_root: Path | None = None
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
    """Run the diagnostic path and persist every handoff.

    The function is intentionally the only coordinator for this vertical slice:
    component services still own validation, authorization, execution, artifacts,
    reporting, outcomes, and knowledge semantics respectively.
    """

    icm_store = ICMStore(request.icm_root or request.report_path.parent / "icm")
    icm_store.initialize_system()
    icm_store.initialize_project(request.project)
    metering = TokenUsageService(memory)
    resolver = ContextResolver(icm_store, structured_retriever=OperationalMemoryRetriever(memory))
    intake_contract = ArtifactContract(
        capability="dataset-characterization",
        reads=["00_task/objective.md", "00_task/constraints.md"],
        does=["validate dataset", "characterize dataset"],
        writes=["10_context/dataset_profile.md"],
    )
    icm_store.validate_contract(request.project.project_id, intake_contract)
    intake_context = resolver.resolve(
        ContextRequest(
            project_id=request.project.project_id,
            assignment="validate and characterize the project dataset",
            capability="dataset-characterization",
            keywords=[request.project.problem_type, "validation", "evidence"],
            system_paths=["constitution.md", "policies/validation.md", "policies/evidence.md"],
            project_paths=["00_task/objective.md", "00_task/constraints.md"],
            required_inputs=[request.manifest.provenance.source_path or "dataset manifest"],
            expected_outputs=["10_context/dataset_profile.md"],
        )
    )
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
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=f"dataset-validation-{version.dataset_version_id}",
        action_type="dataset_validation",
        reason="local deterministic validation does not invoke an LLM or token-metered runtime",
    )
    characterization = characterize_dataset(
        request.manifest,
        request.dataset_root,
        characterization_id=f"characterization-{version.dataset_version_id}",
    )
    _persist_characterization(characterization, memory)
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=characterization.characterization_id,
        action_type="dataset_characterization",
        reason=(
            "local deterministic characterization does not invoke an LLM or token-metered runtime"
        ),
    )
    icm_store.write_artifact(
        request.project.project_id,
        "10_context/dataset_profile.md",
        _dataset_profile_artifact(characterization),
        overwrite=True,
        contract=intake_contract,
    )

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
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=plan.experiment_plan_id,
        action_type="experiment_plan_compilation",
        reason=(
            "local deterministic plan compilation does not invoke an LLM or token-metered runtime"
        ),
    )

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
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=decision.decision_id,
        action_type="decision_evaluation",
        reason=(
            "local deterministic decision evaluation does not invoke an LLM "
            "or token-metered runtime"
        ),
    )

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
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=tool_result.tool_run_id,
        action_type="tool_execution",
        reason="tool execution is not an LLM or token-metered runtime action",
    )
    artifact = _persist_tool_artifact(tool_result, request, plan, decision, memory)
    experiment_root = f"20_work/experiments/{plan.experiment_plan_id}"
    experiment_contract = ArtifactContract(
        capability="modeling",
        reads=["10_context/dataset_profile.md"],
        does=["run approved experiment"],
        writes=[
            f"{experiment_root}/hypothesis.md",
            f"{experiment_root}/config.yaml",
            f"{experiment_root}/inputs.md",
            f"{experiment_root}/results.md",
        ],
    )
    icm_store.validate_contract(request.project.project_id, experiment_contract)
    icm_store.initialize_experiment(
        request.project.project_id,
        plan.experiment_plan_id,
        hypothesis=plan.hypothesis,
        config={
            "experiment_plan_id": plan.experiment_plan_id,
            "dataset_version_id": version.dataset_version_id,
            "execution_backend": plan.execution_backend,
        },
        inputs=[version.manifest_path, *intake_context.required_inputs],
        contract=experiment_contract,
    )
    icm_store.record_experiment_result(
        request.project.project_id,
        plan.experiment_plan_id,
        status=tool_result.status,
        result=_tool_result_artifact(tool_result),
        artifact_refs=tool_result.artifact_refs,
        contract=experiment_contract,
    )
    claim = EvidenceClaim(
        claim_id=f"claim-{plan.experiment_plan_id}",
        project_id=request.project.project_id,
        claim="The baseline experiment produced durable diagnostic evidence.",
        evidence=[
            EvidenceItem(
                source=tool_result.tool_run_id,
                type="tool_run",
                result=f"status={tool_result.status}; metrics={tool_result.metrics}",
            ),
            EvidenceItem(
                source=artifact.artifact_id, type="artifact", result=artifact.artifact_uri
            ),
        ],
        confidence="medium",
        status=EvidenceStatus.SUPPORTED
        if tool_result.status == "succeeded"
        else EvidenceStatus.WEAK,
        experiment_ids=[plan.experiment_plan_id],
    )
    claim_path = icm_store.write_claim(claim)
    diagnostic_context = resolver.resolve(
        ContextRequest(
            project_id=request.project.project_id,
            assignment="interpret baseline evidence and recommend the next governed action",
            capability="scientist-review",
            experiment_id=plan.experiment_plan_id,
            keywords=["evidence", "validation", request.project.problem_type],
            system_paths=[
                "policies/evidence.md",
                "policies/escalation.md",
                "organizational_rules/review.md",
            ],
            project_paths=[
                "00_task/objective.md",
                "10_context/dataset_profile.md",
                f"{experiment_root}/hypothesis.md",
                f"{experiment_root}/results.md",
                f"30_evidence/claims/{claim.claim_id}.yaml",
            ],
            required_inputs=[
                str(claim_path.relative_to(icm_store.projects_root / request.project.project_id))
            ],
            expected_outputs=["40_output/recommendation.md"],
            structured_memory_refs=[
                plan.experiment_plan_id,
                tool_result.tool_run_id,
                artifact.artifact_id,
            ],
        )
    )

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
        system_context_refs=[document.path for document in diagnostic_context.system_documents],
        project_context_refs=[document.path for document in diagnostic_context.project_documents],
        agent_context={
            "assignment": diagnostic_context.assignment,
            "required_inputs": diagnostic_context.required_inputs,
            "expected_outputs": diagnostic_context.expected_outputs,
            "structured_memory_refs": diagnostic_context.structured_memory_refs,
        },
        artifact_refs=[artifact.artifact_uri],
    )
    review = request.provider.review(packet, experiment_ids=[plan.experiment_plan_id])
    _persist_review(review, memory)
    metering.record_provider_action(
        project_id=review.project_id,
        action_id=review.review_id,
        action_type="scientist_review",
        provider_profile_id=review.provider_profile_id,
        model_name=review.model_name,
        usage=review.provider_token_usage,
    )

    post_plan = _compile_post_review_plan(request, version.dataset_version_id, review)
    post_decision = _post_review_decision(request, post_plan)
    _persist_plan(post_plan, memory)
    _persist_decision(post_decision, memory)
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=post_plan.experiment_plan_id,
        action_type="post_review_plan_compilation",
        reason=(
            "local deterministic plan compilation does not invoke an LLM or token-metered runtime"
        ),
    )
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=post_decision.decision_id,
        action_type="post_review_decision_evaluation",
        reason=(
            "local deterministic decision evaluation does not invoke an LLM "
            "or token-metered runtime"
        ),
    )

    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=f"report-{plan.experiment_plan_id}",
        action_type="report_generation",
        reason="fixed-template report rendering does not invoke an LLM or token-metered runtime",
    )
    report = _report_data(
        request,
        version.dataset_version_id,
        characterization,
        plan,
        decision,
        review,
        metering.project_report(request.project.project_id),
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
        reason="Diagnostic completed; no deployment was authorized.",
        owner=request.created_by,
        evidence=[report_artifact.artifact_uri, artifact.artifact_uri],
        related_report_id=report.report_id,
        related_experiment_id=plan.experiment_plan_id,
    )
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=outcome_event.event_id,
        action_type="outcome_transition",
        reason="structured outcome transition does not invoke an LLM or token-metered runtime",
    )
    proposal = _knowledge_proposal(request, review, outcome_event.event_id)
    proposal = KnowledgeCurator().propose(proposal)
    _persist_knowledge_proposal(proposal, request, memory)
    metering.record_not_applicable(
        project_id=request.project.project_id,
        action_id=proposal.proposal_id,
        action_type="knowledge_proposal",
        reason="template-based proposal creation does not invoke an LLM or token-metered runtime",
    )
    review_contract = ArtifactContract(
        capability="critique",
        reads=[
            "10_context/dataset_profile.md",
            f"{experiment_root}/results.md",
            f"30_evidence/claims/{claim.claim_id}.yaml",
        ],
        does=["review evidence", "recommend next action"],
        writes=[
            f"{experiment_root}/critique.md",
            "40_output/recommendation.md",
            "40_output/limitations.md",
            "40_output/handoff.md",
            "10_context/current_state.md",
        ],
    )
    icm_store.validate_contract(request.project.project_id, review_contract)
    icm_store.write_artifact(
        request.project.project_id,
        "40_output/recommendation.md",
        f"# Recommendation\n\n{review.recommended_next_action}\n\n"
        f"Diagnosis: {review.primary_diagnosis}\n\n"
        f"Evidence claim: {claim.claim_id}\n",
        overwrite=True,
        contract=review_contract,
    )
    icm_store.write_artifact(
        request.project.project_id,
        "40_output/limitations.md",
        "# Limitations\n\n"
        + ("\n".join(f"- {note}" for note in review.uncertainty_notes) or "- None recorded.")
        + "\n",
        overwrite=True,
        contract=review_contract,
    )
    icm_store.write_artifact(
        request.project.project_id,
        "40_output/handoff.md",
        f"# Handoff\n\nNext action: {review.recommended_next_action}\n"
        f"Decision: {post_decision.decision_id}\nReview: {review.review_id}\n",
        overwrite=True,
        contract=review_contract,
    )
    icm_store.record_critique(
        request.project.project_id,
        plan.experiment_plan_id,
        f"Provider diagnosis: {review.primary_diagnosis}\n\n"
        f"Evidence references: {review.evidence_references}",
        contract=review_contract,
    )
    icm_store.write_artifact(
        request.project.project_id,
        "10_context/current_state.md",
        "# Current State\n\n"
        f"Baseline {plan.experiment_plan_id} completed with status {tool_result.status}.\n"
        f"Current recommendation: {review.recommended_next_action}.\n",
        overwrite=True,
        contract=review_contract,
    )

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


def _dataset_profile_artifact(characterization: DatasetCharacterizationContract) -> str:
    return "\n".join(
        [
            "# Dataset Profile",
            "",
            characterization.quality_profile.summary or "No quality summary was produced.",
            "",
            "## Findings",
            "",
            *[f"- {finding}" for finding in characterization.identified_issues],
            "",
        ]
    )


def _tool_result_artifact(result: ToolRunResult) -> str:
    return "\n".join(
        [
            "# Experiment Results",
            "",
            f"Status: {result.status}",
            f"Tool run: {result.tool_run_id}",
            f"Metrics: {result.metrics}",
            f"Artifacts: {result.artifact_refs}",
            "",
        ]
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
    token_usage: TokenUsageReport,
) -> StaticReportData:
    def section(summary: str, **content: Any) -> ReportSection:
        return ReportSection(section_status="complete", summary=summary, content=content)

    empty = ReportSection(
        section_status="not_run",
        summary="Not run in this diagnostic phase.",
        missing_or_blocked_reason="This analysis was outside the diagnostic phase scope.",
    )
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
        eda_findings=section(
            "Deterministic dataset characterization completed.",
            class_balance=characterization.class_balance,
            missingness=characterization.missingness_summary,
            distribution_metrics=characterization.distribution_profile.metrics,
            quality_findings=characterization.quality_profile.findings,
        ),
        surprising_findings=ReportSection(
            section_status="not_available",
            summary="No separate surprise-analysis rule was run in this diagnostic workflow.",
            missing_or_blocked_reason=(
                "Characterization findings are reported above without inferring surprise."
            ),
        ),
        proposed_approaches=section(
            "The baseline was proposed to establish a controlled evidence floor.",
            rationale=plan.reason_for_experiment,
            research_basis="No external literature retrieval was invoked in this workflow.",
        ),
        experiment_summary=section(
            "Approved baseline tool run completed.", plan_id=plan.experiment_plan_id
        ),
        experiments_tried=section(
            "One approved baseline tool run was attempted.",
            tool_id=plan.planned_tool_runs[0].tool_id,
            rationale=plan.reason_for_experiment,
        ),
        results_and_interpretation=section(
            "Baseline output was recorded for subsequent review.",
            metrics="See the experiment result and diagnostic packet artifacts.",
        ),
        model_comparison=empty,
        performance_gap_diagnosis=section(
            review.primary_diagnosis, confidence=review.diagnosis_confidence
        ),
        learning_curves=empty,
        error_analysis=empty,
        cluster_or_latent_analysis=empty,
        scientist_review=section("Provider recommendation recorded.", review_id=review.review_id),
        scientific_criticism=ReportSection(
            section_status="not_run",
            summary="No independent critic task was run in this legacy diagnostic workflow.",
            missing_or_blocked_reason=(
                "The legacy synchronous diagnostic path predates runtime-scheduled criticism."
            ),
        ),
        decision_record=section(
            "Experiment decision recorded.",
            decision_id=decision.decision_id,
            allowed=decision.allowed,
        ),
        knowledge_context=empty,
        recommendation=section(review.recommended_next_action, recommendation_only=True),
        project_outcome=section("Validated, not deployed."),
        token_telemetry=ReportSection(
            section_status=(
                "partial_success" if token_usage.unavailable_action_count else "complete"
            ),
            summary=(
                f"Measured total: {token_usage.total_tokens} tokens "
                f"({token_usage.input_tokens} input, {token_usage.output_tokens} output, "
                f"{token_usage.cached_input_tokens} cached input)."
            ),
            missing_or_blocked_reason=(
                "Some agent/provider actions have no authoritative receipt."
                if token_usage.unavailable_action_count
                else None
            ),
            content=token_usage.model_dump(mode="json"),
        ),
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
