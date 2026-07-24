"""Canonical LASI wire contracts.

The contracts are deliberately independent of persistence and execution code.  They
are the boundary between OpenCode procedures, services, and stored artifacts.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base class for all contracts and their nested records."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True)
    schema_version: str = "1.0"


class StringEnum(StrEnum):
    pass


class PrivacyMode(StringEnum):
    LOCAL_ONLY = "local_only"
    SUMMARY_ONLY = "summary_only_to_scientist"
    PLOTS = "plots_allowed"
    THUMBNAILS = "thumbnails_allowed"
    RAW_SAMPLES = "raw_samples_allowed"
    KNOWLEDGE = "knowledge_allowed"


class Provenance(StrictModel):
    author: str | None = None
    created_at: datetime | None = None
    source_path: str | None = None
    source_records: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)


class BudgetEstimate(StrictModel):
    cost_usd: float | None = Field(default=None, ge=0)
    cpu_hours: float | None = Field(default=None, ge=0)
    gpu_hours: float | None = Field(default=None, ge=0)
    wall_time_minutes: float | None = Field(default=None, ge=0)
    memory_gb: float | None = Field(default=None, ge=0)
    storage_gb: float | None = Field(default=None, ge=0)
    human_review_hours: float | None = Field(default=None, ge=0)


class EvaluationPolicy(StrictModel):
    policy_id: str
    name: str | None = None
    primary_metric: str
    secondary_metrics: list[str] = Field(default_factory=list)
    threshold_policy: str | None = None
    class_weighting: str | None = None
    false_positive_cost: float | None = Field(default=None, ge=0)
    false_negative_cost: float | None = Field(default=None, ge=0)
    confidence_interval_required: bool = False
    calibration_required: bool = False
    minimum_meaningful_improvement: float | None = Field(default=None, ge=0)
    success_criteria: str | None = None


class ProjectConfig(StrictModel):
    project_id: str
    project_name: str
    problem_type: str
    modality: str
    dataset_id: str | None = None
    privacy_mode: PrivacyMode = PrivacyMode.LOCAL_ONLY
    evaluation_policy: EvaluationPolicy | None = None
    evaluation_policy_id: str | None = None
    scientist_provider_profile_id: str | None = None
    remote_host_profile_id: str | None = None
    budget: BudgetEstimate | None = None
    harness_version: str | None = None
    toolbox_version: str | None = None


class DatasetFile(StrictModel):
    path: str
    checksum: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    media_type: str | None = None


class DatasetSample(StrictModel):
    sample_id: str
    label: str | int | None = None
    point_cloud_ref: str | None = None
    wafer_id: str | None = None
    lot_id: str | None = None
    tool_id: str | None = None
    recipe_id: str | None = None
    layer_id: str | None = None
    x_location: float | None = None
    y_location: float | None = None
    defect_width: float | None = None
    defect_height: float | None = None
    metadata_ref: str | None = None
    split: str | None = None


class DatasetManifest(StrictModel):
    project_id: str
    dataset_version_id: str
    dataset_id: str | None = None
    source_description: str | None = None
    file_list: list[DatasetFile]
    samples: list[DatasetSample] = Field(default_factory=list)
    label_schema: dict[str, Any] | None = None
    privacy_tags: list[str] = Field(default_factory=list)
    owner_contact: str | None = None
    notes: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class DatasetVersion(StrictModel):
    dataset_version_id: str
    dataset_id: str
    version: str
    project_id: str | None = None
    parent_version_id: str | None = None
    data_hash: str
    manifest_path: str
    created_at: datetime
    created_by: str
    change_type: str
    change_summary: str
    created_because: str | None = None
    comparability_status: str = "unknown"
    status: str = "draft"
    role: str | None = None
    benchmark: bool = False
    approval_id: str | None = None


class CharacterizationProfile(StrictModel):
    summary: str | None = None
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class DatasetCharacterization(StrictModel):
    characterization_id: str
    project_id: str
    dataset_version_id: str
    sample_size: int = Field(ge=0)
    class_balance: dict[str, int | float] = Field(default_factory=dict)
    missingness_summary: dict[str, int | float | str] = Field(default_factory=dict)
    primitive_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    distribution_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    cluster_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    quality_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    coverage_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    separability_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    ambiguity_profile: CharacterizationProfile = Field(default_factory=CharacterizationProfile)
    identified_issues: list[str] = Field(default_factory=list)
    status: str = "complete"
    provenance: Provenance = Field(default_factory=Provenance)


class DatasetImprovementProposal(StrictModel):
    proposal_id: str
    dataset_version_id: str
    project_id: str | None = None
    hypothesis: str
    recommended_change: str
    expected_effect: str
    success_metric: str
    comparability_risk: str
    required_approval: bool = True
    status: str = "draft"
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class ToolSpec(StrictModel):
    tool_id: str
    name: str
    version: str
    description: str | None = None
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    supported_modalities: list[str] = Field(default_factory=list)
    supported_problem_types: list[str] = Field(default_factory=list)
    supported_execution_backends: list[str] = Field(default_factory=lambda: ["local"])
    expected_artifacts: list[str] = Field(default_factory=list)
    approval_status: str = "approved"
    deprecated: bool = False
    failure_modes: list[str] = Field(default_factory=list)
    entrypoint: str | None = None


class ArtifactRecord(StrictModel):
    artifact_id: str
    artifact_uri: str
    artifact_type: str
    checksum: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    project_id: str | None = None
    dataset_version_id: str | None = None
    experiment_id: str | None = None
    tool_run_id: str | None = None
    scientist_review_id: str | None = None
    decision_id: str | None = None
    report_id: str | None = None
    immutable: bool = True


class ToolRunResult(StrictModel):
    tool_run_id: str
    project_id: str
    experiment_id: str | None = None
    experiment_plan_id: str | None = None
    dataset_version_id: str
    tool_id: str
    tool_version: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    execution_backend: str
    status: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    runtime_seconds: float | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    mlflow_run_id: str | None = None
    failure_reason: str | None = None
    partial_success: dict[str, Any] | None = None


class PlannedToolRun(StrictModel):
    tool_id: str = Field(validation_alias=AliasChoices("tool_id", "tool"))
    run_id: str | None = None
    inputs: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExperimentPlan(StrictModel):
    experiment_plan_id: str = Field(validation_alias=AliasChoices("experiment_plan_id", "plan_id"))
    project_id: str
    ticket_id: str | None = None
    dataset_version: str = Field(
        validation_alias=AliasChoices("dataset_version", "dataset_version_id")
    )
    hypothesis: str
    reason_for_experiment: str
    experiment_type: str
    planned_tool_runs: list[PlannedToolRun] = Field(
        default_factory=list, validation_alias=AliasChoices("planned_tool_runs", "tool_runs")
    )
    execution_backend: str
    remote_host_profile: str | None = None
    expected_artifacts: list[str] = Field(default_factory=list)
    expected_signal: str
    success_criteria: str
    failure_criteria: str
    budget_estimate: BudgetEstimate = Field(default_factory=BudgetEstimate)
    privacy_mode: PrivacyMode = PrivacyMode.LOCAL_ONLY
    approval_required: bool = False
    decision_record_required: bool = True
    stop_condition: str | None = None
    handoff_after_decision: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class RemoteHostProfile(StrictModel):
    host_profile_id: str
    hostname: str
    username: str
    ssh_port: int = Field(default=22, ge=1, le=65535)
    authentication_reference: str | None = None
    remote_workspace: str
    environment_setup_command: str | None = None
    python_command: str = "python"
    hardware_summary: str | None = None
    data_transfer_policy: str | None = None
    trust_level: str
    enabled: bool = True


class RemoteRunSpec(StrictModel):
    remote_run_id: str
    project_id: str
    experiment_id: str | None = None
    tool_run_id: str
    host_profile_id: str
    remote_workspace: str
    staged_inputs: list[str] = Field(default_factory=list)
    command: str
    environment_setup: str | None = None
    expected_artifacts: list[str] = Field(default_factory=list)
    dataset_transfer_mode: str | None = None
    cleanup_policy: str = "keep_all"
    status: str = "planned"
    created_at: datetime | None = None


class DiagnosticPacket(StrictModel):
    diagnostic_packet_id: str
    project_id: str
    problem_type: str
    dataset_version_id: str
    dataset_characterization_summary: str | None = None
    evaluation_policy: EvaluationPolicy | None = None
    model_comparison: list[dict[str, Any]] = Field(default_factory=list)
    learning_curve_summary: dict[str, Any] | None = None
    error_analysis_summary: dict[str, Any] | None = None
    cluster_analysis_summary: dict[str, Any] | None = None
    calibration_summary: dict[str, Any] | None = None
    experiment_history: list[str] = Field(default_factory=list)
    current_project_state: str | None = None
    budget_remaining: BudgetEstimate | None = None
    allowed_recommendation_types: list[str] = Field(default_factory=list)
    privacy_mode: PrivacyMode
    open_questions: list[str] = Field(default_factory=list)
    knowledge_context_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class ProviderProfile(StrictModel):
    provider_id: str
    provider_type: str
    model_name: str
    endpoint: str | None = None
    authentication_reference: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    determinism_settings: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=60, gt=0)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    token_budget: int | None = Field(default=None, ge=0)
    privacy_capabilities: list[PrivacyMode] = Field(default_factory=list)
    allowed_input_types: list[str] = Field(default_factory=list)
    response_format: str = "json"
    enabled: bool = True


class ProviderError(StrictModel):
    error_id: str
    provider_id: str
    error_type: str
    message: str
    retryable: bool = False
    fallback_provider_id: str | None = None
    created_at: datetime | None = None
    raw_response_artifact: str | None = None


class AlternativeHypothesis(StrictModel):
    hypothesis: str
    confidence: float = Field(ge=0, le=1)
    supporting_evidence: list[str] = Field(default_factory=list)
    test_that_would_distinguish_it: str


class ScientistReview(StrictModel):
    review_id: str
    project_id: str
    experiment_ids: list[str] = Field(default_factory=list)
    provider_profile_id: str
    model_name: str
    prompt_template_version: str
    diagnostic_packet_id: str
    primary_diagnosis: str
    diagnosis_confidence: float = Field(ge=0, le=1)
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[AlternativeHypothesis] = Field(default_factory=list)
    recommended_next_action: str
    expected_value: str
    estimated_cost: BudgetEstimate | None = None
    stop_recommendation: str | None = None
    escalation_required: bool = False
    human_review_required: bool = False
    knowledge_references: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    raw_response_artifact: str | None = None
    created_at: datetime | None = None


class ApprovalRecord(StrictModel):
    approval_id: str
    project_id: str
    proposal_id: str | None = None
    action_type: str
    risk_level: str
    requested_by: str
    approved_by: str | None = None
    approval_status: str
    approval_reason: str | None = None
    conditions: list[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime | None = None
    related_policy: str | None = None
    related_artifacts: list[str] = Field(default_factory=list)


class DecisionRecord(StrictModel):
    decision_id: str
    project_id: str
    recommendation_id: str | None = None
    experiment_plan_id: str | None = None
    decision_type: str = "operational"
    risk_level: str
    action_requested: str | None = None
    decision: str
    allowed: bool
    approval_required: bool = False
    approved_by: str | None = None
    approval_date: date | None = None
    approval_expiration: date | None = None
    blocked_by: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    policy_checks: dict[str, str | bool] = Field(default_factory=dict)
    privacy_checks: dict[str, str | bool] = Field(default_factory=dict)
    budget_checks: dict[str, str | bool] = Field(default_factory=dict)
    remote_execution_checks: dict[str, str | bool] = Field(default_factory=dict)
    rationale: str
    conditions: list[str] = Field(default_factory=list)
    next_action: str | None = None
    handoff_target: str | None = None
    created_at: datetime | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class ReportSection(StrictModel):
    section_status: str
    source_records: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)
    summary: str | None = None
    missing_or_blocked_reason: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)


class StaticReportData(StrictModel):
    report_id: str
    report_header: dict[str, Any]
    executive_summary: ReportSection
    current_decision: ReportSection
    dataset_summary: ReportSection
    dataset_characterization: ReportSection
    experiment_summary: ReportSection
    model_comparison: ReportSection
    performance_gap_diagnosis: ReportSection
    learning_curves: ReportSection
    error_analysis: ReportSection
    cluster_or_latent_analysis: ReportSection
    scientist_review: ReportSection
    decision_record: ReportSection
    knowledge_context: ReportSection
    recommendation: ReportSection
    project_outcome: ReportSection
    appendix: ReportSection
    project_outcome_status: str = "pending"
    provenance: Provenance = Field(default_factory=Provenance)
    report_state: str = "generated"


class ProjectOutcome(StrictModel):
    project_id: str
    current_status: str = "pending"
    final_disposition: str | None = None
    deployment_status: str = "not_deployed"
    production_status: str = "not_in_production"
    reason_category: str | None = None
    result_summary: str | None = None
    cancellation_reason: str | None = None
    failure_reason: str | None = None
    blocked_reason: str | None = None
    owner: str
    decision_date: date | None = None
    last_updated_at: datetime
    related_reports: list[str] = Field(default_factory=list)
    related_artifacts: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)


class OutcomeEvent(StrictModel):
    event_id: str
    project_id: str
    previous_status: str | None = None
    new_status: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    owner: str
    created_at: datetime
    related_report_id: str | None = None
    related_experiment_id: str | None = None
    related_deployment_id: str | None = None
    notes: str | None = None


class KnowledgeDocument(StrictModel):
    document_id: str
    type: str
    status: str
    owner: str
    created_at: date
    last_reviewed_at: date | None = None
    source_projects: list[str] = Field(default_factory=list)
    source_datasets: list[str] = Field(default_factory=list)
    related_modalities: list[str] = Field(default_factory=list)
    related_problem_types: list[str] = Field(default_factory=list)
    related_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    evidence_level: str | None = None
    path: str
    git_commit: str | None = None


class KnowledgeProposal(StrictModel):
    proposal_id: str
    proposal_type: str
    project_id: str | None = None
    source: str
    recommendation_id: str | None = None
    title: str
    summary: str
    evidence_references: list[str] = Field(default_factory=list)
    rationale: str
    expected_value: str | None = None
    impact: str | None = None
    risk: str | None = None
    affected_documents: list[str] = Field(default_factory=list)
    recommended_approvers: list[str] = Field(default_factory=list)
    approval_required: bool = True
    status: str = "draft"
    provenance: Provenance = Field(default_factory=Provenance)


ContractT = TypeVar("ContractT", bound=StrictModel)


CONTRACTS: dict[str, type[StrictModel]] = {
    "ProjectConfig": ProjectConfig,
    "DatasetManifest": DatasetManifest,
    "DatasetVersion": DatasetVersion,
    "DatasetCharacterization": DatasetCharacterization,
    "DatasetImprovementProposal": DatasetImprovementProposal,
    "ToolSpec": ToolSpec,
    "ToolRunResult": ToolRunResult,
    "ExperimentPlan": ExperimentPlan,
    "RemoteRunSpec": RemoteRunSpec,
    "RemoteHostProfile": RemoteHostProfile,
    "DiagnosticPacket": DiagnosticPacket,
    "ProviderProfile": ProviderProfile,
    "ProviderError": ProviderError,
    "ScientistReview": ScientistReview,
    "DecisionRecord": DecisionRecord,
    "ApprovalRecord": ApprovalRecord,
    "ArtifactRecord": ArtifactRecord,
    "StaticReportData": StaticReportData,
    "ProjectOutcome": ProjectOutcome,
    "OutcomeEvent": OutcomeEvent,
    "KnowledgeDocument": KnowledgeDocument,
    "KnowledgeProposal": KnowledgeProposal,
    "EvaluationPolicy": EvaluationPolicy,
}
