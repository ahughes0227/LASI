"""Deterministic exploration and plan authorization."""

from __future__ import annotations

from collections import Counter
from uuid import uuid4

from .contracts import (
    ApprovalStatus,
    ExplorationDirective,
    ExplorationKind,
    FindingSeverity,
    MemoryContext,
    Plan,
    TrustLevel,
    VerificationFinding,
    VerificationResult,
    content_digest,
    utc_now,
)
from .identity import ApprovalService, AuthenticationError, IdentityService
from .ledger import AuthorityStore
from .operators import OperatorRegistry


class ExplorationPolicy:
    def __init__(self, *, stagnation_runs: int = 3) -> None:
        self.stagnation_runs = stagnation_runs

    def directives(
        self, memory: MemoryContext, registry: OperatorRegistry
    ) -> tuple[ExplorationDirective, ...]:
        directives: list[ExplorationDirective] = []
        weak = [
            belief
            for belief in memory.beliefs
            if belief.invalid_at is None and belief.confidence < 0.5
        ]
        if weak:
            directives.append(
                ExplorationDirective(
                    directive_id=str(uuid4()),
                    kind=ExplorationKind.CHALLENGE_BELIEF,
                    reason="Active beliefs have weak support.",
                    target_refs=tuple(item.belief_id for item in weak),
                    strength=0.8,
                )
            )
        external = [item for item in memory.evidence if item.trust == TrustLevel.UNTRUSTED]
        if external:
            directives.append(
                ExplorationDirective(
                    directive_id=str(uuid4()),
                    kind=ExplorationKind.TEST_EXTERNAL_CLAIM,
                    reason="External context must be tested before it can influence authority.",
                    target_refs=tuple(item.evidence_id for item in external),
                    strength=0.9,
                )
            )
        recent = memory.recent_runs[-self.stagnation_runs :]
        if len(recent) == self.stagnation_runs and len({run.outcome for run in recent}) == 1:
            used = Counter(name for run in recent for name in run.operator_names)
            unused = [spec.name for spec in registry.specs() if spec.name not in used]
            directives.append(
                ExplorationDirective(
                    directive_id=str(uuid4()),
                    kind=(
                        ExplorationKind.TRY_UNUSED_OPERATOR
                        if unused
                        else ExplorationKind.TRY_ANALOGY
                    ),
                    reason="Recent outcomes are stagnant; change the search neighborhood.",
                    target_refs=tuple(unused),
                    strength=1.0,
                )
            )
        return tuple(directives)


class PlanVerifier:
    def __init__(
        self,
        registry: OperatorRegistry,
        store: AuthorityStore,
        identities: IdentityService,
        approvals: ApprovalService,
    ) -> None:
        self.registry = registry
        self.store = store
        self.identities = identities
        self.approvals = approvals

    def verify(self, plan: Plan) -> VerificationResult:
        findings: list[VerificationFinding] = []
        try:
            requester = self.identities.snapshot(plan.requester_id)
            profile = self.store.planner_profile(plan.planner_profile_id)
            if profile is None:
                raise AuthenticationError("planner profile is not registered")
            profile_identity = self.identities.snapshot(profile.service_identity_id)
        except AuthenticationError as exc:
            invalid = content_digest({"identity_error": str(exc)})
            finding = VerificationFinding(
                code="identity_invalid",
                message=str(exc),
                severity=FindingSeverity.ERROR,
            )
            return VerificationResult(
                decision_id=content_digest(
                    {
                        "plan": plan.digest(),
                        "policy": self.identities.policy_version,
                        "finding": finding,
                    }
                ),
                plan_id=plan.plan_id,
                plan_digest=plan.digest(),
                allowed=False,
                findings=(finding,),
                policy_version=self.identities.policy_version,
                requester_snapshot_digest=invalid,
                planner_snapshot_digest=invalid,
            )
        known_evidence = {item.evidence_id for item in self.store.evidence(plan.goal.project_id)}
        for step in plan.steps:
            try:
                spec = self.registry.get(step.operator).spec
            except KeyError:
                findings.append(
                    VerificationFinding(
                        code="unknown_operator",
                        message=f"Operator is not registered: {step.operator}",
                        severity=FindingSeverity.ERROR,
                        step_id=step.step_id,
                    )
                )
                continue
            for label, snapshot in (("requester", requester), ("planner", profile_identity)):
                if not any(
                    grant.permits(spec.name, spec.risk, plan.goal.project_id, utc_now())
                    for grant in snapshot.execution_grants
                ):
                    findings.append(
                        VerificationFinding(
                            code=f"{label}_denied",
                            message=f"{label} is not granted {spec.name} at {spec.risk} risk.",
                            severity=FindingSeverity.ERROR,
                            step_id=step.step_id,
                        )
                    )
            if set(step.evidence_refs) - known_evidence:
                findings.append(
                    VerificationFinding(
                        code="unknown_evidence",
                        message="Plan cites evidence outside authoritative memory.",
                        severity=FindingSeverity.ERROR,
                        step_id=step.step_id,
                    )
                )
            required = self.approvals.required_count(spec.risk, spec.requires_approval)
            if required:
                request = self.store.approval_request(plan.plan_id, step.step_id)
                if request and request.status == ApprovalStatus.DENIED:
                    findings.append(
                        VerificationFinding(
                            code="approval_denied",
                            message="Approval request was denied.",
                            severity=FindingSeverity.ERROR,
                            step_id=step.step_id,
                        )
                    )
                elif request is None or not self.approvals.satisfied(request):
                    findings.append(
                        VerificationFinding(
                            code="approval_required",
                            message=f"Operator {spec.name} requires {required} approval(s).",
                            severity=FindingSeverity.APPROVAL,
                            step_id=step.step_id,
                        )
                    )
        errors = any(item.severity == FindingSeverity.ERROR for item in findings)
        approval_needed = any(item.severity == FindingSeverity.APPROVAL for item in findings)
        decision_id = content_digest(
            {
                "plan": plan.digest(),
                "policy": self.identities.policy_version,
                "requester": requester.digest(),
                "planner": profile_identity.digest(),
                "findings": findings,
                "allowed": not errors and not approval_needed,
            }
        )
        return VerificationResult(
            decision_id=decision_id,
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            allowed=not errors and not approval_needed,
            requires_approval=approval_needed and not errors,
            findings=tuple(findings),
            policy_version=self.identities.policy_version,
            requester_snapshot_digest=requester.digest(),
            planner_snapshot_digest=profile_identity.digest(),
        )

    def ensure_approval_requests(self, plan: Plan) -> tuple[str, ...]:
        request_ids: list[str] = []
        for step in plan.steps:
            spec = self.registry.get(step.operator).spec
            required = self.approvals.required_count(spec.risk, spec.requires_approval)
            if required:
                request = self.approvals.ensure_request(
                    plan_id=plan.plan_id,
                    plan_digest=plan.digest(),
                    step_id=step.step_id,
                    project_id=plan.goal.project_id,
                    requester_id=plan.requester_id,
                    risk=spec.risk,
                    required=required,
                )
                request_ids.append(request.request_id)
        return tuple(request_ids)
