"""Contracts between memory, planning, policy, and execution."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


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


class Goal(Contract):
    goal_id: str
    project_id: str
    objective: str = Field(min_length=1)
    success_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


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
    valid_at: datetime = Field(default_factory=utc_now)
    invalid_at: datetime | None = None


class IdentityGrant(Contract):
    subject_id: str
    operators: frozenset[str]
    max_risk: RiskLevel = RiskLevel.LOW
    project_ids: frozenset[str] = frozenset()
    expires_at: datetime | None = None

    def permits(self, *, operator: str, risk: RiskLevel, project_id: str, at: datetime) -> bool:
        return (
            (operator in self.operators or "*" in self.operators)
            and RISK_ORDER[risk] <= RISK_ORDER[self.max_risk]
            and (not self.project_ids or project_id in self.project_ids)
            and (self.expires_at is None or at < self.expires_at)
        )


class IdentitySnapshot(Contract):
    actor_id: str
    roles: frozenset[str] = frozenset()
    grants: tuple[IdentityGrant, ...] = ()
    policy_version: str


class RunSummary(Contract):
    run_id: str
    plan_id: str
    status: str
    operator_names: tuple[str, ...] = ()
    outcome: str | None = None


class MemoryContext(Contract):
    project_id: str
    beliefs: tuple[Belief, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    recent_runs: tuple[RunSummary, ...] = ()
    constraints: tuple[str, ...] = ()
    retrieved_at: datetime = Field(default_factory=utc_now)


class ExplorationKind(StrEnum):
    CHALLENGE_BELIEF = "challenge_belief"
    TEST_EXTERNAL_CLAIM = "test_external_claim"
    TRY_UNUSED_OPERATOR = "try_unused_operator"
    SEEK_DISCONFIRMING_EVIDENCE = "seek_disconfirming_evidence"
    TRY_ANALOGY = "try_analogy"


class ExplorationDirective(Contract):
    kind: ExplorationKind
    reason: str
    target_refs: tuple[str, ...] = ()
    strength: float = Field(default=0.5, ge=0, le=1)


class OperatorSpec(Contract):
    name: str
    description: str
    version: str
    risk: RiskLevel = RiskLevel.LOW
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    idempotent: bool = True
    requires_approval: bool = False


class PlanStep(Contract):
    step_id: str
    operator: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    rationale: str
    evidence_refs: tuple[str, ...] = ()
    approval_ref: str | None = None


class Plan(Contract):
    plan_id: str
    goal: Goal
    proposed_by: str
    steps: tuple[PlanStep, ...]
    exploration_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def unique_steps(self) -> Plan:
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step ids must be unique")
        return self

    def digest(self) -> str:
        value = self.model_dump(mode="json", exclude={"created_at"})
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


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
    plan_id: str
    plan_digest: str
    allowed: bool
    requires_approval: bool = False
    findings: tuple[VerificationFinding, ...] = ()
    policy_version: str
    verified_at: datetime = Field(default_factory=utc_now)


class ApprovalRecord(Contract):
    approval_id: str
    plan_digest: str
    step_id: str
    approver_id: str
    approved_at: datetime = Field(default_factory=utc_now)


class OperatorInvocation(Contract):
    run_id: str
    project_id: str
    step: PlanStep
    idempotency_key: str


class OperatorResult(Contract):
    status: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifact_uris: tuple[str, ...] = ()
    failure_reason: str | None = None


class StepRun(Contract):
    step_id: str
    operator: str
    status: str
    result: OperatorResult | None = None
    reused: bool = False


class ExecutionResult(Contract):
    run_id: str
    plan_id: str
    status: str
    steps: tuple[StepRun, ...]


class LedgerEvent(Contract):
    event_id: str
    project_id: str
    kind: str
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=utc_now)
