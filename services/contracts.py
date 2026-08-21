"""Strict contracts between LASI authority, planning, memory, and execution."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    def default(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, (set, frozenset, tuple)):
            return list(item)
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError(f"{type(item).__name__} is not JSON serializable")

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=default,
    )


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class TrustLevel(StrEnum):
    UNTRUSTED = "untrusted"
    CORROBORATED = "corroborated"
    AUTHORITATIVE = "authoritative"


class SessionStatus(StrEnum):
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    DENIED = "denied"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalChoice(StrEnum):
    APPROVE = "approve"
    DENY = "deny"


class ProjectionStatus(StrEnum):
    CURRENT = "current"
    LAGGING = "lagging"
    DEGRADED = "degraded"


class Goal(Contract):
    goal_id: str
    project_id: str
    objective: str = Field(min_length=1)
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    def digest(self) -> str:
        return content_digest(self)


class Evidence(Contract):
    evidence_id: str
    project_id: str
    source: str
    content: str
    trust: TrustLevel = TrustLevel.UNTRUSTED
    observed_at: datetime = Field(default_factory=utc_now)
    artifact_uri: str | None = None


class Belief(Contract):
    belief_id: str
    project_id: str
    statement: str
    confidence: float = Field(ge=0, le=1)
    status: str = "hypothesis"
    evidence_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    valid_at: datetime = Field(default_factory=utc_now)
    invalid_at: datetime | None = None


class IdentityRecord(Contract):
    subject_id: str
    credential_id: str
    public_key_base64: str
    active: bool = True
    version: int = 1
    roles: frozenset[str] = frozenset()


class ExecutionGrant(Contract):
    grant_id: str
    subject_id: str
    operators: frozenset[str]
    max_risk: RiskLevel = RiskLevel.LOW
    project_ids: frozenset[str] = frozenset()
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def permits(self, operator: str, risk: RiskLevel, project_id: str, at: datetime) -> bool:
        return (
            self.revoked_at is None
            and (operator in self.operators or "*" in self.operators)
            and RISK_ORDER[risk] <= RISK_ORDER[self.max_risk]
            and (not self.project_ids or project_id in self.project_ids)
            and (self.expires_at is None or at < self.expires_at)
        )


class ApprovalGrant(Contract):
    grant_id: str
    subject_id: str
    max_risk: RiskLevel
    project_ids: frozenset[str] = frozenset()
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def permits(self, risk: RiskLevel, project_id: str, at: datetime) -> bool:
        return (
            self.revoked_at is None
            and RISK_ORDER[risk] <= RISK_ORDER[self.max_risk]
            and (not self.project_ids or project_id in self.project_ids)
            and (self.expires_at is None or at < self.expires_at)
        )


class IdentitySnapshot(Contract):
    subject_id: str
    credential_id: str
    identity_version: int
    roles: frozenset[str]
    execution_grants: tuple[ExecutionGrant, ...]
    approval_grants: tuple[ApprovalGrant, ...]
    policy_version: str

    def digest(self) -> str:
        return content_digest(self)


class SignedAction(Contract):
    action_id: str
    actor_id: str
    credential_id: str
    action: str
    payload_digest: str
    nonce: str
    issued_at: datetime
    expires_at: datetime
    signature_base64: str

    def signing_bytes(self) -> bytes:
        return canonical_json(self.model_dump(mode="json", exclude={"signature_base64"})).encode()

    @classmethod
    def unsigned(
        cls,
        *,
        action_id: str,
        actor_id: str,
        credential_id: str,
        action: str,
        payload_digest: str,
        nonce: str,
        ttl: timedelta = timedelta(minutes=5),
        issued_at: datetime | None = None,
    ) -> SignedAction:
        now = issued_at or utc_now()
        return cls(
            action_id=action_id,
            actor_id=actor_id,
            credential_id=credential_id,
            action=action,
            payload_digest=payload_digest,
            nonce=nonce,
            issued_at=now,
            expires_at=now + ttl,
            signature_base64=base64.b64encode(bytes(64)).decode(),
        )


class RunSummary(Contract):
    run_id: str
    plan_id: str
    project_id: str
    status: SessionStatus
    operator_names: tuple[str, ...] = ()
    outcome: str | None = None
    finished_at: datetime = Field(default_factory=utc_now)


class ProjectionHealth(Contract):
    status: ProjectionStatus = ProjectionStatus.CURRENT
    authoritative_sequence: int = 0
    projected_sequence: int = 0
    pending_count: int = 0
    dead_letter_count: int = 0
    last_success_at: datetime | None = None
    last_error: str | None = None


class MemoryContext(Contract):
    project_id: str
    beliefs: tuple[Belief, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    recent_runs: tuple[RunSummary, ...] = ()
    constraints: tuple[str, ...] = ()
    authoritative_sequence: int = 0
    projection: ProjectionHealth = Field(default_factory=ProjectionHealth)
    retrieval_warnings: tuple[str, ...] = ()
    retrieved_at: datetime = Field(default_factory=utc_now)


class ExplorationKind(StrEnum):
    CHALLENGE_BELIEF = "challenge_belief"
    TEST_EXTERNAL_CLAIM = "test_external_claim"
    TRY_UNUSED_OPERATOR = "try_unused_operator"
    SEEK_DISCONFIRMING_EVIDENCE = "seek_disconfirming_evidence"
    TRY_ANALOGY = "try_analogy"


class ExplorationDirective(Contract):
    directive_id: str
    kind: ExplorationKind
    reason: str
    target_refs: tuple[str, ...] = ()
    strength: float = Field(default=0.5, ge=0, le=1)


class OperatorSpec(Contract):
    name: str
    description: str
    version: str
    entrypoint: str
    implementation_digest: str
    risk: RiskLevel = RiskLevel.LOW
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    idempotent: bool = True
    requires_approval: bool = False
    timeout_seconds: float = Field(default=300, gt=0, le=86_400)
    max_memory_mb: int = Field(default=2048, ge=64)
    max_output_bytes: int = Field(default=1_000_000, ge=1024)
    environment_keys: frozenset[str] = frozenset()


class PlanStep(Contract):
    step_id: str
    operator: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    rationale: str
    evidence_refs: tuple[str, ...] = ()


class Plan(Contract):
    plan_id: str
    goal: Goal
    requester_id: str
    planner_profile_id: str
    steps: tuple[PlanStep, ...]
    exploration_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_steps(self) -> Plan:
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step ids must be unique")
        prior: set[str] = set()
        all_ids = set(ids)
        for step in self.steps:
            if set(step.depends_on) - all_ids or set(step.depends_on) - prior:
                raise ValueError("step dependencies must refer to earlier steps")
            prior.add(step.step_id)
        return self

    def digest(self) -> str:
        return content_digest(self.model_dump(mode="json", exclude={"created_at"}))


class FindingSeverity(StrEnum):
    ERROR = "error"
    APPROVAL = "approval"
    WARNING = "warning"


class VerificationFinding(Contract):
    code: str
    message: str
    severity: FindingSeverity
    step_id: str | None = None


class VerificationResult(Contract):
    decision_id: str
    plan_id: str
    plan_digest: str
    allowed: bool
    requires_approval: bool = False
    findings: tuple[VerificationFinding, ...] = ()
    policy_version: str
    requester_snapshot_digest: str
    planner_snapshot_digest: str
    verified_at: datetime = Field(default_factory=utc_now)


class ApprovalRequest(Contract):
    request_id: str
    plan_id: str
    plan_digest: str
    step_id: str
    project_id: str
    requester_id: str
    risk: RiskLevel
    required_approvals: int
    policy_version: str
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime


class ApprovalDecision(Contract):
    approval_id: str
    request_id: str
    approver_id: str
    choice: ApprovalChoice
    reason: str
    identity_snapshot_digest: str
    signed_action_id: str
    decided_at: datetime = Field(default_factory=utc_now)


class PlannerProfile(Contract):
    profile_id: str
    service_identity_id: str
    model: str
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout_seconds: float = Field(default=120, gt=0)
    max_transient_attempts: int = Field(default=3, ge=1, le=5)
    max_repair_attempts: int = Field(default=2, ge=0, le=3)
    api_base: str | None = None

    def digest(self) -> str:
        return content_digest(self)


class ModelInvocation(Contract):
    invocation_id: str
    session_id: str
    profile_id: str
    model: str
    template_version: str
    attempt: int
    request_digest: str
    response_digest: str | None = None
    status: str
    error_category: str | None = None
    error_message: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None
    latency_ms: int
    created_at: datetime = Field(default_factory=utc_now)


class ArtifactReceipt(Contract):
    digest: str
    uri: str
    size_bytes: int


class OperatorResult(Contract):
    status: StepStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: tuple[str, ...] = ()
    artifacts: tuple[ArtifactReceipt, ...] = ()
    failure_code: str | None = None
    failure_reason: str | None = None


class StepRun(Contract):
    step_id: str
    operator: str
    status: StepStatus
    result: OperatorResult | None = None
    reused: bool = False


class ExecutionResult(Contract):
    run_id: str
    plan_id: str
    status: SessionStatus
    steps: tuple[StepRun, ...]


class LedgerEvent(Contract):
    event_id: str
    project_id: str
    kind: str
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=utc_now)
