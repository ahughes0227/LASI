"""Canonical LASI wire contracts.

The contracts are deliberately independent of persistence and execution code.  They
are the boundary between OpenCode procedures, services, and stored artifacts.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from .agent_roles import validate_agent_role


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
    project_id: str | None = None
    challenge_id: str | None = None
    dataset_version_id: str | None = None
    experiment_plan_id: str | None = None
    tool_run_id: str | None = None
    decision_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    code_version: str | None = None
    environment_ref: str | None = None


class PredictionArtifact(StrictModel):
    prediction_artifact_id: str
    challenge_id: str
    model_run_id: str
    source_test_dataset_version: str
    row_count: int = Field(ge=0)
    identifier_columns: list[str] = Field(default_factory=list)
    prediction_columns: list[str]
    prediction_dtype: str
    row_order_policy: str
    checksum: str
    generating_tool: str
    generating_tool_version: str
    artifact_uri: str
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class SubmissionValidation(StrictModel):
    validation_id: str
    challenge_id: str
    prediction_artifact_id: str
    status: str
    expected_columns: list[str] = Field(default_factory=list)
    observed_columns: list[str] = Field(default_factory=list)
    expected_row_count: int | None = Field(default=None, ge=0)
    observed_row_count: int | None = Field(default=None, ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checksum: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class EvaluatorSpec(StrictModel):
    evaluator_id: str
    name: str
    version: str
    problem_type: str
    primary_metric: str
    deterministic: bool = True
    implementation_ref: str
    enabled: bool = True
    provenance: Provenance = Field(default_factory=Provenance)


class EvaluationResult(StrictModel):
    evaluation_run_id: str
    challenge_id: str
    prediction_artifact_id: str
    evaluator_id: str
    evaluator_version: str
    status: str
    primary_metric: str
    primary_value: float | None = None
    secondary_metrics: dict[str, float] = Field(default_factory=dict)
    sample_count: int = Field(ge=0)
    score_artifact_checksum: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class BudgetEstimate(StrictModel):
    cost_usd: float | None = Field(default=None, ge=0)
    cpu_hours: float | None = Field(default=None, ge=0)
    gpu_hours: float | None = Field(default=None, ge=0)
    wall_time_minutes: float | None = Field(default=None, ge=0)
    memory_gb: float | None = Field(default=None, ge=0)
    storage_gb: float | None = Field(default=None, ge=0)
    human_review_hours: float | None = Field(default=None, ge=0)


class ChallengeSpec(StrictModel):
    """User-supplied challenge definition; never inferred from a challenge name."""

    challenge_id: str
    project_id: str
    title: str
    brief: str
    problem_type: str
    modalities: list[str]
    train_sources: list[str]
    test_sources: list[str]
    supplemental_sources: list[str] = Field(default_factory=list)
    sample_submission_source: str | None = None
    target_columns: list[str] = Field(default_factory=list)
    identifier_columns: list[str] = Field(default_factory=list)
    group_columns: list[str] = Field(default_factory=list)
    time_columns: list[str] = Field(default_factory=list)
    prediction_columns: list[str] = Field(default_factory=list)
    evaluation_metric: str
    evaluation_direction: str
    submission_format: str
    privacy_mode: PrivacyMode = PrivacyMode.LOCAL_ONLY
    allowed_tools: list[str] = Field(default_factory=list)
    compute_budget: BudgetEstimate = Field(default_factory=BudgetEstimate)
    random_seed_policy: str
    external_data_policy: str
    internet_policy: str
    hidden_label_policy: str
    provenance: Provenance = Field(default_factory=Provenance)


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
    capability_state: str = "production_ready"
    deprecated: bool = False
    failure_modes: list[str] = Field(default_factory=list)
    entrypoint: str | None = None

    @model_validator(mode="after")
    def validate_capability_state(self) -> "ToolSpec":
        if self.capability_state not in {
            "production_ready",
            "experimental",
            "stub",
            "unavailable",
        }:
            raise ValueError("unsupported tool capability_state")
        return self


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


class ComponentPort(StrictModel):
    """A typed artifact boundary exposed by a reusable executable component."""

    name: str
    artifact_type: str
    required: bool = True
    description: str | None = None


class ComponentRuntimeSpec(StrictModel):
    """Trusted runtime metadata selected by registration, never by an invocation."""

    language: str = "python"
    execution_mode: str = "in_process"
    entrypoint: str | None = None
    toolchain: str | None = None
    minimum_version: str | None = None
    build_command_id: str | None = None
    protocol_version: str = "1.0"

    @model_validator(mode="after")
    def validate_runtime(self) -> "ComponentRuntimeSpec":
        if self.language not in {"python", "typescript", "rust", "go"}:
            raise ValueError("unsupported component runtime language")
        if self.execution_mode not in {"in_process", "subprocess"}:
            raise ValueError("unsupported component execution mode")
        if self.execution_mode == "in_process" and self.language != "python":
            raise ValueError("only Python components may execute in process")
        return self


class ComponentOperationalRequirements(StrictModel):
    """Small scheduling and reporting hints, not a sandbox policy."""

    writes_artifacts: bool = False
    requires_network: bool = False
    requires_subprocess: bool = False
    accelerator: str = "none"

    @model_validator(mode="after")
    def validate_requirements(self) -> "ComponentOperationalRequirements":
        if self.accelerator not in {"none", "optional", "cpu", "gpu", "tpu"}:
            raise ValueError("unsupported component accelerator requirement")
        return self


class ComponentSpec(StrictModel):
    """Discoverable metadata for an approved, versioned component implementation."""

    component_id: str
    name: str
    version: str
    description: str | None = None
    responsibility: str | None = None
    does_not: list[str] = Field(default_factory=list)
    configuration_boundary: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    inputs: list[ComponentPort] = Field(default_factory=list)
    outputs: list[ComponentPort] = Field(default_factory=list)
    supported_modalities: list[str] = Field(default_factory=list)
    supported_problem_types: list[str] = Field(default_factory=list)
    supported_execution_backends: list[str] = Field(default_factory=lambda: ["local"])
    resource_requirements: BudgetEstimate = Field(default_factory=BudgetEstimate)
    runtime: ComponentRuntimeSpec = Field(default_factory=ComponentRuntimeSpec)
    operational_requirements: ComponentOperationalRequirements = Field(
        default_factory=ComponentOperationalRequirements
    )
    source_ref: str | None = None
    source_hash: str | None = None
    dependency_lock_hash: str | None = None
    build_artifact_hash: str | None = None
    toolchain_version: str | None = None
    lifecycle: str = "approved"
    owner: str | None = None
    replacement_component_id: str | None = None
    known_limitations: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)


class ComponentCandidate(StrictModel):
    """Planner retrieval evidence kept separate from compatibility resolution."""

    catalog_node_id: str
    component_id: str
    version: str
    retrieval_score: float = Field(ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    responsibility_compatibility: float = Field(default=0, ge=0, le=1)
    configuration_compatibility: float = Field(default=0, ge=0, le=1)
    input_coverage: float = Field(default=0, ge=0, le=1)
    output_coverage: float = Field(default=0, ge=0, le=1)
    conflicting_exclusions: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class ComponentResolution(StrictModel):
    """Mandatory component deduplication decision before implementation."""

    resolution_id: str
    requested_component_id: str
    action: str
    candidates: list[ComponentCandidate] = Field(default_factory=list)
    selected_component_ids: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    affected_capability_ids: list[str] = Field(default_factory=list)
    affected_workflow_ids: list[str] = Field(default_factory=list)
    rationale: str
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_resolution(self) -> "ComponentResolution":
        if self.action not in {"reuse", "compose", "extend", "new"}:
            raise ValueError("unsupported component resolution")
        if self.action in {"reuse", "compose", "extend"} and not self.selected_component_ids:
            raise ValueError(f"{self.action} resolution requires selected components")
        if self.action == "new" and self.selected_component_ids:
            raise ValueError("new resolution cannot select existing components")
        return self


class ComponentResearchDecision(StrictModel):
    """Source-backed answer to one component implementation gap."""

    decision_id: str
    question: str
    alternatives: list[str] = Field(min_length=1)
    selected_approach: str
    rationale: list[str] = Field(min_length=1)
    rejected: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = Field(min_length=1)
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_research_decision(self) -> "ComponentResearchDecision":
        if self.selected_approach not in self.alternatives:
            raise ValueError("selected approach must be one of the alternatives")
        return self


class ComponentBuildPlan(StrictModel):
    """Frozen authority for one component package build."""

    build_id: str
    component: ComponentSpec
    resolution: ComponentResolution
    registration_scope: str = "shared_toolbox"
    research_questions: list[str] = Field(default_factory=list)
    research_decision_refs: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    affected_capability_ids: list[str] = Field(default_factory=list)
    affected_workflow_ids: list[str] = Field(default_factory=list)
    tests_required: list[str] = Field(default_factory=list)
    evaluation_requirements: list[str] = Field(default_factory=list)
    status: str = "planned"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_build_plan(self) -> "ComponentBuildPlan":
        if self.resolution.requested_component_id != self.component.component_id:
            raise ValueError("resolution does not belong to component")
        if self.registration_scope != "shared_toolbox":
            raise ValueError("component builder only creates shared registered components")
        if self.resolution.action in {"reuse", "compose", "extend"} and self.files_to_create:
            raise ValueError(f"{self.resolution.action} resolution must not create a package")
        return self


class ComponentValidation(StrictModel):
    """Deterministic evidence required before registration can be proposed."""

    validation_id: str
    build_id: str
    component_id: str
    package_hash: str
    checks: dict[str, bool]
    test_refs: list[str] = Field(default_factory=list)
    evaluation_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values()) and not self.errors


class ComponentRegistrationProposal(StrictModel):
    """Hash-bound request to add a component to the shared execution registry."""

    proposal_id: str
    build_id: str
    component_id: str
    component_version: str
    package_path: str
    package_hash: str
    resolution_ref: str
    validation_ref: str
    registration_scope: str = "shared_toolbox"
    required_action: str = "update_toolbox"
    status: str = "pending_approval"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class ComponentRegistrationRecord(StrictModel):
    """Durable record of registration and derived planner projection status."""

    registration_id: str
    proposal_id: str
    component_id: str
    component_version: str
    package_hash: str
    planner_projection_status: str
    planner_projection_error: str | None = None
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class ComponentBuildEvidence(StrictModel):
    """Observed source, dependency, toolchain, and build outputs for a package."""

    source_hash: str
    dependency_lock_hash: str | None = None
    build_artifact_hash: str | None = None
    toolchain: str | None = None
    toolchain_version: str | None = None
    status: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)


class CapabilitySpec(StrictModel):
    """Canonical semantic contract for a requested or registered LASI capability."""

    capability_id: str = Field(pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    purpose: str
    accepts: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    operations: list[str] = Field(min_length=1)
    guarantees: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    does_not: list[str] = Field(default_factory=list)
    capability_dependencies: list[str] = Field(default_factory=list)
    component_dependencies: list[str] = Field(default_factory=list)
    execution_kind: str = "component_pipeline"
    lifecycle: str = "draft"
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_capability_spec(self) -> "CapabilitySpec":
        if self.capability_id in self.capability_dependencies:
            raise ValueError("capability cannot depend on itself")
        if set(self.operations) & set(self.does_not):
            raise ValueError("operations and does_not must not overlap")
        if self.lifecycle not in {"draft", "experimental", "approved", "deprecated"}:
            raise ValueError("unsupported capability lifecycle")
        if self.execution_kind not in {
            "component_pipeline",
            "opencode_skill",
            "python_service",
            "external_adapter",
        }:
            raise ValueError("unsupported capability execution kind")
        return self


class CapabilityCandidate(StrictModel):
    """One structurally compared candidate considered during mandatory deduplication."""

    capability_id: str
    version: str
    overall_score: float = Field(ge=0, le=1)
    purpose_score: float = Field(ge=0, le=1)
    input_coverage: float = Field(ge=0, le=1)
    output_coverage: float = Field(ge=0, le=1)
    operation_coverage: float = Field(ge=0, le=1)
    guarantee_coverage: float = Field(ge=0, le=1)
    constraint_coverage: float = Field(ge=0, le=1)
    side_effect_compatibility: float = Field(ge=0, le=1)
    conflicting_exclusions: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class CapabilityResolution(StrictModel):
    """Required REUSE/EXTEND/COMPOSE/NEW decision made before research or building."""

    resolution_id: str
    requested_capability_id: str
    action: str
    candidates: list[CapabilityCandidate] = Field(default_factory=list)
    selected_capability_ids: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    rationale: str
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_resolution(self) -> "CapabilityResolution":
        if self.action not in {"reuse", "extend", "compose", "new"}:
            raise ValueError("unsupported capability resolution")
        if self.action in {"reuse", "extend", "compose"} and not self.selected_capability_ids:
            raise ValueError(f"{self.action} resolution requires selected capabilities")
        if self.action == "new" and self.selected_capability_ids:
            raise ValueError("new resolution cannot select an existing capability")
        return self


class CapabilityResearchDecision(StrictModel):
    """Source-backed answer to one implementation gap, not an unbounded research essay."""

    decision_id: str
    question: str
    alternatives: list[str] = Field(min_length=1)
    selected_approach: str
    rationale: list[str] = Field(min_length=1)
    rejected: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = Field(min_length=1)
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_research_decision(self) -> "CapabilityResearchDecision":
        if self.selected_approach not in self.alternatives:
            raise ValueError("selected approach must be one of the researched alternatives")
        return self


class CapabilityBuildPlan(StrictModel):
    """Frozen authority for one capability build after deduplication."""

    build_id: str
    capability: CapabilitySpec
    resolution: CapabilityResolution
    registration_scope: str = "shared_toolbox"
    reused_capability_ids: list[str] = Field(default_factory=list)
    reused_component_ids: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    research_decision_refs: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    affected_capability_ids: list[str] = Field(default_factory=list)
    tests_required: list[str] = Field(default_factory=list)
    evaluation_requirements: list[str] = Field(default_factory=list)
    status: str = "planned"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_build_plan(self) -> "CapabilityBuildPlan":
        if self.resolution.requested_capability_id != self.capability.capability_id:
            raise ValueError("resolution does not belong to capability")
        if self.registration_scope not in {"project_experimental", "shared_toolbox"}:
            raise ValueError("unsupported capability registration scope")
        if self.resolution.action in {"reuse", "extend"} and self.files_to_create:
            raise ValueError(
                f"{self.resolution.action} resolution must not create a duplicate package"
            )
        return self


class CapabilityValidation(StrictModel):
    """Deterministic evidence required before registration can be proposed."""

    validation_id: str
    build_id: str
    capability_id: str
    package_hash: str
    checks: dict[str, bool]
    test_refs: list[str] = Field(default_factory=list)
    evaluation_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values()) and not self.errors


class CapabilityRegistrationProposal(StrictModel):
    """Governed request to add a validated capability to the shared runtime surface."""

    proposal_id: str
    build_id: str
    capability_id: str
    capability_version: str
    package_path: str
    package_hash: str
    resolution_ref: str
    validation_ref: str
    registration_scope: str
    required_action: str = "update_toolbox"
    status: str = "pending_approval"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class ComponentRequest(StrictModel):
    """Coordinator request for a bounded new component implementation."""

    request_id: str
    project_id: str
    requested_scope: str = "project_experimental"
    component: ComponentSpec
    source_ref: str
    source_hash: str
    dependencies: list[str] = Field(default_factory=list)
    test_refs: list[str] = Field(default_factory=list)
    expected_resource_use: BudgetEstimate = Field(default_factory=BudgetEstimate)
    requires_network: bool = False
    requires_subprocess: bool = False
    requires_external_provider: bool = False
    requires_secrets: bool = False
    includes_native_code: bool = False
    writes_outside_workdir: bool = False
    mutates_shared_state: bool = False
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_component_request(self) -> "ComponentRequest":
        if self.requested_scope not in {"project_experimental", "shared_toolbox"}:
            raise ValueError("unsupported component request scope")
        if self.component.lifecycle not in {"draft", "experimental"}:
            raise ValueError("requested component must have draft or experimental lifecycle")
        return self


class ComponentReview(StrictModel):
    """Durable automatic review decision; it does not execute component code."""

    review_id: str
    request_id: str
    project_id: str
    component_id: str
    component_version: str
    source_hash: str
    decision: str
    allowed: bool
    risk_level: str
    security_checks: dict[str, bool] = Field(default_factory=dict)
    stability_checks: dict[str, bool] = Field(default_factory=dict)
    blocked_by: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    rationale: str
    reviewed_by: str = "component-reviewer"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class ComponentInvocation(StrictModel):
    """One node in an immutable experiment component graph."""

    node_id: str
    component_id: str
    component_version: str
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)


class ExperimentSpec(StrictModel):
    """Fully-resolved executable configuration, separate from experiment intent."""

    experiment_spec_id: str
    project_id: str
    dataset_version_id: str
    hypothesis: str
    modality: str
    problem_type: str
    component_graph: list[ComponentInvocation]
    execution_backend: str = "local"
    random_seed: int | None = None
    evaluation_policy: EvaluationPolicy | None = None
    expected_outputs: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)


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


class ResearchLoopPolicy(StrictModel):
    """Assignment-scoped autonomy and evidence-based plateau policy."""

    objective_metric: str
    objective_direction: str
    minimum_meaningful_improvement: float = Field(default=0, ge=0)
    plateau_patience: int = Field(default=4, ge=3, le=4)
    max_iterations: int = Field(default=24, ge=1)
    # Autonomy backstops enforced when the runtime leases work.  The turn cap
    # bounds every assignment, including agent runtimes that return no usage
    # receipt; the token ceiling additionally bounds metered spend.
    max_agent_turns: int = Field(default=200, ge=1)
    token_ceiling: int = Field(default=5_000_000, ge=1)
    initial_novelty_floor: float = Field(default=0.25, ge=0, le=1)
    novelty_increment: float = Field(default=0.15, ge=0, le=1)
    maximum_novelty_floor: float = Field(default=0.85, ge=0, le=1)

    @model_validator(mode="after")
    def validate_loop_policy(self) -> "ResearchLoopPolicy":
        if self.objective_direction not in {"maximize", "minimize"}:
            raise ValueError("objective_direction must be maximize or minimize")
        if self.maximum_novelty_floor < self.initial_novelty_floor:
            raise ValueError("maximum_novelty_floor must not be below initial_novelty_floor")
        return self


class ResearchAttempt(StrictModel):
    """One reviewed explore-research-theorize-test attempt."""

    attempt_id: str
    iteration: int = Field(ge=1)
    experiment_plan_id: str
    status: str
    score: float | None = None
    hypothesis: str
    research_basis: list[str] = Field(default_factory=list)
    approach_signature: list[str] = Field(default_factory=list)
    novel_dimensions: list[str] = Field(default_factory=list)
    novelty_score: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)
    failure_reason: str | None = None


class ResearchLoopState(StrictModel):
    """Reconstructable state and next routing decision for an autonomous assignment."""

    project_id: str
    policy: ResearchLoopPolicy
    attempts: list[ResearchAttempt] = Field(default_factory=list)
    best_score: float | None = None
    best_attempt_id: str | None = None
    non_improving_novel_attempts: int = Field(default=0, ge=0)
    required_novelty: float = Field(default=0, ge=0, le=1)
    status: str = "running"
    next_phase: str | None = "explore"
    reason: str | None = None


class ResearchAlternative(StrictModel):
    """One evaluated alternative considered before asking for human intervention."""

    description: str
    feasible: bool
    authorized: bool
    rejection_reason: str | None = None


class ResearchEscalation(StrictModel):
    """A request for human discretion, with the alternatives already ruled out.

    Escalation is the one way an assignment stops for a reason other than
    completion or an exhausted budget, so it carries its own justification: the
    alternatives that were considered and why each was rejected.  An escalation
    is invalid while any considered alternative remains both feasible and
    authorized, because that alternative is work the assignment may simply do.
    """

    escalation_id: str
    question: str
    necessity: str
    alternatives_considered: list[ResearchAlternative] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_alternatives(self) -> "ResearchEscalation":
        if not self.question.strip():
            raise ValueError("escalation requires a question for the human")
        if not self.alternatives_considered:
            raise ValueError("escalation requires the alternatives that were evaluated")
        remaining = [
            item.description
            for item in self.alternatives_considered
            if item.feasible and item.authorized
        ]
        if remaining:
            raise ValueError(
                "escalation is invalid while a feasible authorized alternative remains: "
                + ", ".join(remaining)
            )
        return self


class ReasoningCriterion(StrictModel):
    """One explicit step in an agent's reasoning or result-acceptance protocol."""

    criterion_id: str
    instruction: str
    evaluation_mode: str = "evidentiary"
    required: bool = True

    @model_validator(mode="after")
    def validate_evaluation_mode(self) -> "ReasoningCriterion":
        if self.evaluation_mode not in {"deterministic", "evidentiary", "judgment"}:
            raise ValueError("unsupported rubric evaluation_mode")
        return self


class ReasoningRubric(StrictModel):
    """Versioned reasoning guidance and acceptance contract for one capability."""

    rubric_id: str
    version: str
    capability: str
    purpose: str
    criteria: list[ReasoningCriterion]


class WorkflowPromptRef(StrictModel):
    """Immutable reference to a versioned workflow instruction asset."""

    prompt_id: str
    version: str


class WorkflowRubricRef(StrictModel):
    """Immutable reference to a versioned workflow acceptance asset."""

    rubric_id: str
    version: str


class AgentProfile(StrictModel):
    """Invocation policy for a workflow worker; never an authority grant."""

    profile_id: str
    version: str
    agent_role: str
    allowed_skills: list[str] = Field(default_factory=list)
    context_policy: dict[str, Any] = Field(default_factory=dict)
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactContract(StrictModel):
    """Typed handoff paths for one workflow node."""

    artifact_id: str
    artifact_type: str
    uri_pattern: str | None = None
    required: bool = True


class WorkflowActivation(StrictModel):
    """Declarative, inspectable activation predicate for a node."""

    when: str = "always"
    reason: str | None = None


class WorkflowSkipPolicy(StrictModel):
    """Explicit handling for conditional, failed, and blocked work."""

    allowed_statuses: list[str] = Field(
        default_factory=lambda: ["blocked", "failed", "not_applicable", "deferred"]
    )
    record_reason: bool = True
    downstream_behavior: str = "continue"


class WorkflowDecisionGate(StrictModel):
    """Decision binding required before a governed node can be proposed."""

    gate_id: str
    action_type: str
    required: bool = True
    allowing_decision_required: bool = False


class WorkflowExtensionPolicy(StrictModel):
    """Boundaries for coordinator-created dynamic tasks."""

    allow_dynamic_tasks: bool = False
    allowed_task_types: list[str] = Field(default_factory=list)
    allow_execution: bool = False
    max_tasks: int = Field(default=0, ge=0)


class WorkflowNode(StrictModel):
    """Declarative unit of workflow routing and typed handoff."""

    node_id: str
    task_type: str
    dependencies: list[str] = Field(default_factory=list)
    reads: list[WorkflowArtifactContract] = Field(default_factory=list)
    writes: list[WorkflowArtifactContract] = Field(default_factory=list)
    prompt: WorkflowPromptRef
    rubric: WorkflowRubricRef
    skill: str
    capability: str
    completion_mode: str = "required"
    activation: WorkflowActivation = Field(default_factory=WorkflowActivation)
    skip_policy: WorkflowSkipPolicy = Field(default_factory=WorkflowSkipPolicy)
    escalation_behavior: str = "record_and_stop"
    experiment_plan_binding: str | None = None
    decision_binding: str | None = None
    decision_gate: WorkflowDecisionGate | None = None
    agent_profile: WorkflowPromptRef | None = None
    priority: int = 0
    max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_completion_mode(self) -> "WorkflowNode":
        if self.completion_mode not in {"required", "conditional", "optional", "dynamic"}:
            raise ValueError("unsupported workflow completion_mode")
        if self.task_type in {"experiment_execution", "tool_execution", "component_execution"}:
            if not self.experiment_plan_binding or not self.decision_binding:
                raise ValueError("execution workflow nodes require plan and decision bindings")
        high_consequence = {
            "dataset_update",
            "dataset_promotion",
            "knowledge_promotion",
            "policy_change",
            "deployment",
            "foundation_training",
        }
        if self.task_type in high_consequence and self.decision_gate is None:
            raise ValueError("high-consequence workflow nodes require a decision gate")
        return self


class WorkflowDefinition(StrictModel):
    """Versioned JSON workflow package; the workflow control-plane authority."""

    workflow_id: str
    version: str
    goal: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    nodes: list[WorkflowNode]
    extension_policy: WorkflowExtensionPolicy = Field(default_factory=WorkflowExtensionPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowCandidate(StrictModel):
    """Structural comparison produced before a workflow build begins."""

    workflow_id: str
    version: str
    task_coverage: float = Field(ge=0, le=1)
    artifact_coverage: float = Field(ge=0, le=1)
    gate_coverage: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    missing_requirements: list[str] = Field(default_factory=list)


class WorkflowResolution(StrictModel):
    """Mandatory deduplication decision for a requested workflow."""

    resolution_id: str
    requested_workflow_id: str
    action: str
    candidates: list[WorkflowCandidate] = Field(default_factory=list)
    selected_workflow_ids: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    rationale: str
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_resolution(self) -> "WorkflowResolution":
        if self.action not in {"reuse", "compose", "extend", "new"}:
            raise ValueError("unsupported workflow resolution")
        if self.action in {"reuse", "compose", "extend"} and not self.selected_workflow_ids:
            raise ValueError("workflow resolution must select an existing workflow")
        if self.action == "new" and self.selected_workflow_ids:
            raise ValueError("new workflow resolution cannot select an existing workflow")
        return self


class WorkflowBuildPlan(StrictModel):
    """Frozen authority for one workflow package build."""

    build_id: str
    workflow: WorkflowDefinition
    resolution: WorkflowResolution
    registration_scope: str = "installed_workflow"
    research_questions: list[str] = Field(default_factory=list)
    research_decision_refs: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    affected_workflow_ids: list[str] = Field(default_factory=list)
    tests_required: list[str] = Field(default_factory=list)
    evaluation_requirements: list[str] = Field(default_factory=list)
    status: str = "planned"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @model_validator(mode="after")
    def validate_build_plan(self) -> "WorkflowBuildPlan":
        if self.resolution.requested_workflow_id != self.workflow.workflow_id:
            raise ValueError("workflow resolution does not belong to workflow")
        if self.resolution.action in {"reuse", "extend"} and self.files_to_create:
            raise ValueError(
                f"{self.resolution.action} resolution must not create a duplicate workflow package"
            )
        return self


class WorkflowValidation(StrictModel):
    """Deterministic evidence required before a workflow registration proposal."""

    validation_id: str
    build_id: str
    workflow_id: str
    package_hash: str
    checks: dict[str, bool]
    test_refs: list[str] = Field(default_factory=list)
    evaluation_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values()) and not self.errors


class WorkflowRegistrationProposal(StrictModel):
    """Governed request to install a validated workflow package."""

    proposal_id: str
    build_id: str
    workflow_id: str
    workflow_version: str
    package_path: str
    package_hash: str
    resolution_ref: str
    validation_ref: str
    registration_scope: str
    status: str = "pending_review"
    created_at: datetime
    provenance: Provenance = Field(default_factory=Provenance)


class TaskSpec(StrictModel):
    """One immutable unit of work proposed by an orchestrator and owned by the runtime."""

    task_id: str
    project_id: str
    task_type: str
    agent_role: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    rubric_id: str
    rubric_version: str
    required_inputs: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    structured_memory_refs: list[str] = Field(default_factory=list)
    experiment_plan_id: str | None = None
    decision_id: str | None = None
    scientific_checkpoint: bool = False
    priority: int = 0
    max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_dispatchable_agent_role(self) -> "TaskSpec":
        # A proposed role becomes an OpenCode agent launch, so it is checked here,
        # at the contract boundary every proposal must cross.
        validate_agent_role(self.agent_role)
        return self


class TaskGraphProposal(StrictModel):
    """Stateless orchestrator proposal; the runtime decides what becomes operational state."""

    proposal_id: str
    assignment_id: str
    project_id: str
    observed_revision: int = Field(ge=1)
    rationale: str
    tasks: list[TaskSpec]
    created_at: datetime | None = None


class AgentArtifact(StrictModel):
    artifact_id: str
    artifact_type: str
    uri: str
    checksum: str | None = None


class CriterionResult(StrictModel):
    criterion_id: str
    status: str
    evidence_refs: list[str] = Field(default_factory=list)
    rationale: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "CriterionResult":
        if self.status not in {"satisfied", "not_satisfied", "not_applicable", "uncertain"}:
            raise ValueError("unsupported criterion result status")
        return self


class ScientificClaim(StrictModel):
    claim_id: str
    statement: str
    claim_type: str = "hypothesis"
    status: str = "proposed"
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def preserve_tentative_knowledge_status(self) -> "ScientificClaim":
        if self.claim_type not in {"observation", "inference", "hypothesis", "lesson_candidate"}:
            raise ValueError("unsupported scientific claim type")
        if self.status not in {
            "proposed",
            "experimentally_supported",
            "challenged",
            "refuted",
            "survived_challenge",
            "replicated",
        }:
            raise ValueError("agent claims cannot directly become accepted facts")
        return self


class ValidityThreat(StrictModel):
    threat_type: str
    severity: str
    description: str
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_severity(self) -> "ValidityThreat":
        if self.severity not in {"low", "medium", "high", "critical"}:
            raise ValueError("unsupported validity threat severity")
        return self


class FalsificationTest(StrictModel):
    test_id: str
    description: str
    supports_claim_when: str
    refutes_claim_when: str
    estimated_cost: str = "low"


class CriticAssessment(StrictModel):
    assessment_id: str
    claim_id: str
    assessment: str
    strongest_counterargument: str
    confidence: float = Field(ge=0, le=1)
    material: bool = True
    alternative_explanations: list[str] = Field(default_factory=list)
    validity_threats: list[ValidityThreat] = Field(default_factory=list)
    falsification_tests: list[FalsificationTest] = Field(default_factory=list)
    recommended_disposition: str
    evidence_refs: list[str] = Field(default_factory=list)


class AgentResult(StrictModel):
    """Structured, non-authoritative result returned to the runtime by an agent."""

    task_id: str
    attempt_id: str
    status: str
    summary: str
    criterion_results: list[CriterionResult]
    artifacts: list[AgentArtifact] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    claims: list[ScientificClaim] = Field(default_factory=list)
    critic_assessment: CriticAssessment | None = None
    task_graph_proposal: TaskGraphProposal | None = None
    experiment_plans: list[ExperimentPlan] = Field(default_factory=list)
    recommended_followup_tasks: list[TaskSpec] = Field(default_factory=list)
    recommended_assignment_status: str | None = None
    # One reviewed attempt in the persistent research loop.  The runtime, not
    # the agent, decides what it means for novelty, plateau, and routing.
    research_attempt: ResearchAttempt | None = None
    escalation: ResearchEscalation | None = None
    knowledge_proposal_refs: list[str] = Field(default_factory=list)
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_result_status(self) -> "AgentResult":
        if self.status not in {"completed", "partial", "failed", "blocked"}:
            raise ValueError("unsupported agent result status")
        if self.status in {"failed", "blocked"} and not self.failure_reason:
            raise ValueError("failed or blocked result requires failure_reason")
        if self.recommended_assignment_status not in {None, "continue", "complete", "escalate"}:
            raise ValueError("unsupported recommended assignment status")
        if (self.recommended_assignment_status == "escalate") != (self.escalation is not None):
            raise ValueError("escalation payload and escalate status must accompany each other")
        return self


class AgentTask(StrictModel):
    """Runtime-issued task lease and minimum-sufficient context references."""

    assignment_id: str
    task: TaskSpec
    attempt_id: str
    lease_owner: str
    lease_expires_at: datetime
    context_snapshot_id: str
    rubric: ReasoningRubric
    structured_state: dict[str, Any] = Field(default_factory=dict)


class ResearchAssignment(StrictModel):
    """Durable user assignment controlled through the OpenCode admin surface."""

    assignment_id: str
    project_id: str
    objective: str
    loop_policy: ResearchLoopPolicy
    status: str = "active"
    pause_requested: bool = False
    cancel_requested: bool = False
    latest_summary: str | None = None
    pending_escalation_id: str | None = None
    pending_escalation_question: str | None = None
    human_response: str | None = None
    # Monotonic version of the assignment's task graph.  A proposal states the
    # revision it was planned against, so a plan built from a view the runtime
    # has already moved past is rejected rather than merged into a graph that
    # no longer matches it.
    graph_revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
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
    system_context_refs: list[str] = Field(default_factory=list)
    project_context_refs: list[str] = Field(default_factory=list)
    agent_context: dict[str, Any] = Field(default_factory=dict)
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


class TokenUsageStatus(StringEnum):
    """Whether LASI received an exact runtime usage receipt for an action."""

    REPORTED = "reported"
    NOT_AVAILABLE = "not_available"
    NOT_APPLICABLE = "not_applicable"


class ProviderTokenUsage(StrictModel):
    """Exact token and billed-cost values returned by a provider or agent runtime.

    These fields intentionally do not contain estimated values.  An adapter that
    cannot obtain an authoritative receipt must omit this object and let the
    action ledger record ``not_available`` instead.
    """

    reporting_source: str
    total_tokens: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    billed_cost_usd: float | None = Field(default=None, ge=0)
    reported_at: datetime | None = None
    source_reference: str | None = None

    @model_validator(mode="after")
    def require_authoritative_source(self) -> "ProviderTokenUsage":
        if not self.reporting_source.strip():
            raise ValueError("reporting_source must identify the provider or runtime receipt")
        if "estimate" in self.reporting_source.lower():
            raise ValueError("estimated token usage must not be recorded as provider usage")
        return self


class ActionTokenUsage(StrictModel):
    """Append-only token metering entry for one traceable LASI action."""

    action_usage_id: str
    project_id: str
    action_id: str
    action_type: str
    status: TokenUsageStatus
    provider_profile_id: str | None = None
    model_name: str | None = None
    usage: ProviderTokenUsage | None = None
    unavailable_reason: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_metering_state(self) -> "ActionTokenUsage":
        if self.status == TokenUsageStatus.REPORTED and self.usage is None:
            raise ValueError("reported token usage requires an authoritative usage receipt")
        if self.status != TokenUsageStatus.REPORTED and self.usage is not None:
            raise ValueError("only reported token usage may include a usage receipt")
        if self.status == TokenUsageStatus.NOT_AVAILABLE and not self.unavailable_reason:
            raise ValueError("not_available token usage requires an explicit reason")
        return self


class AgentInvocationResult(StrictModel):
    """Agent result plus the authoritative receipt captured by its invoker."""

    result: AgentResult
    usage: ProviderTokenUsage | None = None
    raw_response_artifact_ref: str | None = None


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
    provider_token_usage: ProviderTokenUsage | None = None
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


class TokenUsageBreakdown(StrictModel):
    """Exact token use grouped by a durable LASI action type."""

    action_type: str
    action_count: int = Field(ge=0)
    reported_action_count: int = Field(ge=0)
    unavailable_action_count: int = Field(ge=0)
    not_applicable_action_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    billed_cost_usd: float = Field(ge=0)


class TokenUsageReport(StrictModel):
    """Measured token-usage summary for an experiment closeout report."""

    action_count: int = Field(ge=0)
    reported_action_count: int = Field(ge=0)
    unavailable_action_count: int = Field(ge=0)
    not_applicable_action_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    billed_cost_usd: float = Field(ge=0)
    breakdown: list[TokenUsageBreakdown] = Field(default_factory=list)


class StaticReportData(StrictModel):
    report_id: str
    report_header: dict[str, Any]
    executive_summary: ReportSection
    current_decision: ReportSection
    dataset_summary: ReportSection
    dataset_characterization: ReportSection
    eda_findings: ReportSection
    surprising_findings: ReportSection
    proposed_approaches: ReportSection
    experiment_summary: ReportSection
    experiments_tried: ReportSection
    results_and_interpretation: ReportSection
    model_comparison: ReportSection
    performance_gap_diagnosis: ReportSection
    learning_curves: ReportSection
    error_analysis: ReportSection
    cluster_or_latent_analysis: ReportSection
    scientist_review: ReportSection
    scientific_criticism: ReportSection
    decision_record: ReportSection
    knowledge_context: ReportSection
    recommendation: ReportSection
    project_outcome: ReportSection
    token_telemetry: ReportSection
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
    "ChallengeSpec": ChallengeSpec,
    "PredictionArtifact": PredictionArtifact,
    "SubmissionValidation": SubmissionValidation,
    "EvaluatorSpec": EvaluatorSpec,
    "EvaluationResult": EvaluationResult,
    "ProjectConfig": ProjectConfig,
    "DatasetManifest": DatasetManifest,
    "DatasetVersion": DatasetVersion,
    "DatasetCharacterization": DatasetCharacterization,
    "DatasetImprovementProposal": DatasetImprovementProposal,
    "ToolSpec": ToolSpec,
    "ToolRunResult": ToolRunResult,
    "ExperimentPlan": ExperimentPlan,
    "ResearchLoopPolicy": ResearchLoopPolicy,
    "ResearchAttempt": ResearchAttempt,
    "ResearchLoopState": ResearchLoopState,
    "ResearchAlternative": ResearchAlternative,
    "ResearchEscalation": ResearchEscalation,
    "ReasoningCriterion": ReasoningCriterion,
    "ReasoningRubric": ReasoningRubric,
    "TaskSpec": TaskSpec,
    "TaskGraphProposal": TaskGraphProposal,
    "AgentArtifact": AgentArtifact,
    "CriterionResult": CriterionResult,
    "ScientificClaim": ScientificClaim,
    "ValidityThreat": ValidityThreat,
    "FalsificationTest": FalsificationTest,
    "CriticAssessment": CriticAssessment,
    "AgentResult": AgentResult,
    "AgentTask": AgentTask,
    "ResearchAssignment": ResearchAssignment,
    "CapabilitySpec": CapabilitySpec,
    "CapabilityCandidate": CapabilityCandidate,
    "CapabilityResolution": CapabilityResolution,
    "CapabilityResearchDecision": CapabilityResearchDecision,
    "CapabilityBuildPlan": CapabilityBuildPlan,
    "CapabilityValidation": CapabilityValidation,
    "CapabilityRegistrationProposal": CapabilityRegistrationProposal,
    "ComponentSpec": ComponentSpec,
    "ComponentRuntimeSpec": ComponentRuntimeSpec,
    "ComponentOperationalRequirements": ComponentOperationalRequirements,
    "ComponentCandidate": ComponentCandidate,
    "ComponentResolution": ComponentResolution,
    "ComponentResearchDecision": ComponentResearchDecision,
    "ComponentBuildPlan": ComponentBuildPlan,
    "ComponentValidation": ComponentValidation,
    "ComponentRegistrationProposal": ComponentRegistrationProposal,
    "ComponentRegistrationRecord": ComponentRegistrationRecord,
    "ComponentBuildEvidence": ComponentBuildEvidence,
    "ComponentRequest": ComponentRequest,
    "ComponentReview": ComponentReview,
    "ExperimentSpec": ExperimentSpec,
    "RemoteRunSpec": RemoteRunSpec,
    "RemoteHostProfile": RemoteHostProfile,
    "DiagnosticPacket": DiagnosticPacket,
    "ProviderProfile": ProviderProfile,
    "ProviderError": ProviderError,
    "ProviderTokenUsage": ProviderTokenUsage,
    "ActionTokenUsage": ActionTokenUsage,
    "AgentInvocationResult": AgentInvocationResult,
    "AgentProfile": AgentProfile,
    "TokenUsageBreakdown": TokenUsageBreakdown,
    "TokenUsageReport": TokenUsageReport,
    "ScientistReview": ScientistReview,
    "DecisionRecord": DecisionRecord,
    "ApprovalRecord": ApprovalRecord,
    "ArtifactRecord": ArtifactRecord,
    "StaticReportData": StaticReportData,
    "ProjectOutcome": ProjectOutcome,
    "OutcomeEvent": OutcomeEvent,
    "KnowledgeDocument": KnowledgeDocument,
    "KnowledgeProposal": KnowledgeProposal,
    "WorkflowActivation": WorkflowActivation,
    "WorkflowArtifactContract": WorkflowArtifactContract,
    "WorkflowDecisionGate": WorkflowDecisionGate,
    "WorkflowDefinition": WorkflowDefinition,
    "WorkflowBuildPlan": WorkflowBuildPlan,
    "WorkflowCandidate": WorkflowCandidate,
    "WorkflowExtensionPolicy": WorkflowExtensionPolicy,
    "WorkflowNode": WorkflowNode,
    "WorkflowPromptRef": WorkflowPromptRef,
    "WorkflowRegistrationProposal": WorkflowRegistrationProposal,
    "WorkflowResolution": WorkflowResolution,
    "WorkflowRubricRef": WorkflowRubricRef,
    "WorkflowSkipPolicy": WorkflowSkipPolicy,
    "WorkflowValidation": WorkflowValidation,
    "EvaluationPolicy": EvaluationPolicy,
}
