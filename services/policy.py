"""Deterministic exploration pressure and authorization verification."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from .contracts import (
    ExplorationDirective,
    ExplorationKind,
    FindingSeverity,
    IdentitySnapshot,
    MemoryContext,
    Plan,
    RiskLevel,
    TrustLevel,
    VerificationFinding,
    VerificationResult,
)
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
        *,
        approval_checker: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self.registry = registry
        self.approval_checker = approval_checker or (lambda _ref, _digest, _step: False)

    def verify(
        self,
        plan: Plan,
        *,
        identity: IdentitySnapshot,
        memory: MemoryContext,
    ) -> VerificationResult:
        findings: list[VerificationFinding] = []
        known_steps = {step.step_id for step in plan.steps}
        prior_steps: set[str] = set()
        known_evidence = {item.evidence_id for item in memory.evidence}
        now = datetime.now(UTC)

        for step in plan.steps:
            if set(step.depends_on) - known_steps or set(step.depends_on) - prior_steps:
                findings.append(
                    VerificationFinding(
                        code="invalid_dependency",
                        message="Dependencies must refer to earlier steps.",
                        severity=FindingSeverity.ERROR,
                        step_id=step.step_id,
                    )
                )
            prior_steps.add(step.step_id)
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
            permitted = any(
                grant.subject_id == identity.actor_id
                and grant.permits(
                    operator=spec.name,
                    risk=spec.risk,
                    project_id=plan.goal.project_id,
                    at=now,
                )
                for grant in identity.grants
            )
            if not permitted:
                findings.append(
                    VerificationFinding(
                        code="identity_denied",
                        message=f"Identity graph does not grant {spec.name} at {spec.risk} risk.",
                        severity=FindingSeverity.ERROR,
                        step_id=step.step_id,
                    )
                )
            if set(step.evidence_refs) - known_evidence:
                findings.append(
                    VerificationFinding(
                        code="unknown_evidence",
                        message="Plan cites evidence outside the memory snapshot.",
                        severity=FindingSeverity.ERROR,
                        step_id=step.step_id,
                    )
                )
            requires_approval = (
                spec.requires_approval
                or spec.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            )
            approval_valid = (
                step.approval_ref is not None
                and self.approval_checker(step.approval_ref, plan.digest(), step.step_id)
            )
            if requires_approval and not approval_valid:
                findings.append(
                    VerificationFinding(
                        code="approval_required",
                        message=f"Operator {spec.name} requires approval.",
                        severity=FindingSeverity.APPROVAL,
                        step_id=step.step_id,
                    )
                )
        has_errors = any(item.severity == FindingSeverity.ERROR for item in findings)
        needs_approval = any(item.severity == FindingSeverity.APPROVAL for item in findings)
        return VerificationResult(
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            allowed=not has_errors and not needs_approval,
            requires_approval=needs_approval and not has_errors,
            findings=tuple(findings),
            policy_version=identity.policy_version,
        )
