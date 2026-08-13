"""Typed contracts for nested system, project, and agent context."""

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import Field, field_validator

from services.contracts.models import StrictModel


class EvidenceStatus(StrEnum):
    UNSUPPORTED = "unsupported"
    WEAK = "weak"
    CONFLICTING = "conflicting"
    SUPPORTED = "supported"
    STRONGLY_SUPPORTED = "strongly_supported"
    INVALIDATED = "invalidated"


class ICMDocument(StrictModel):
    path: str
    layer: str
    document_type: str
    title: str | None = None
    content: str


class ICMProject(StrictModel):
    project_id: str
    root: str
    directories: list[str] = Field(default_factory=list)


class ContextRequest(StrictModel):
    project_id: str
    assignment: str
    capability: str | None = None
    experiment_id: str | None = None
    keywords: list[str] = Field(default_factory=list)
    system_paths: list[str] = Field(default_factory=list)
    project_paths: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    structured_memory_refs: list[str] = Field(default_factory=list)
    max_documents: int = Field(default=8, ge=0, le=50)


class ContextDocument(StrictModel):
    path: str
    layer: str
    content: str
    relevance: int = Field(ge=0)


class AgentContext(StrictModel):
    project_id: str
    assignment: str
    system_documents: list[ContextDocument] = Field(default_factory=list)
    project_documents: list[ContextDocument] = Field(default_factory=list)
    local_assignment: str
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    structured_memory_refs: list[str] = Field(default_factory=list)


class ArtifactContract(StrictModel):
    capability: str
    reads: list[str] = Field(default_factory=list)
    does: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)

    @field_validator("reads", "writes")
    @classmethod
    def paths_are_relative(cls, paths: list[str]) -> list[str]:
        for path in paths:
            parsed = PurePosixPath(path)
            if parsed.is_absolute() or ".." in parsed.parts:
                raise ValueError(f"artifact path must be relative: {path}")
        return paths


class EvidenceItem(StrictModel):
    source: str
    evidence_type: str = Field(alias="type")
    result: str


class EvidenceClaim(StrictModel):
    claim_id: str
    project_id: str
    claim: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: str
    status: EvidenceStatus
    experiment_ids: list[str] = Field(default_factory=list)
    depends_on_claim_ids: list[str] = Field(default_factory=list)
    invalidated_by: list[str] = Field(default_factory=list)


class ExperimentContext(StrictModel):
    project_id: str
    experiment_id: str
    hypothesis: str
    status: str = "planned"
    inputs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    invalidation_reasons: list[str] = Field(default_factory=list)


class ProjectState(StrictModel):
    """Reconstructed semantic state, derived entirely from durable ICM artifacts."""

    project_id: str
    objective: str | None = None
    constraints: str | None = None
    current_state: str | None = None
    experiments: list[ExperimentContext] = Field(default_factory=list)
    claims: list[EvidenceClaim] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class PromotionProposal(StrictModel):
    proposal_id: str
    project_id: str
    title: str
    principle: str
    source_claim_ids: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    source_projects: list[str] = Field(default_factory=list)
    broadly_reusable: bool = False
    critic_approved: bool = False
    explicitly_requested: bool = False
    status: str = "draft"
