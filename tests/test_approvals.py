from __future__ import annotations

import pytest
from services.contracts import (
    ApprovalChoice,
    Goal,
    OperatorSpec,
    Plan,
    PlanStep,
    RiskLevel,
)
from services.identity import AuthorizationError


def risk_plan(operator: str) -> Plan:
    return Plan(
        plan_id=f"plan-{operator}",
        goal=Goal(goal_id=f"goal-{operator}", project_id="project-1", objective="change"),
        requester_id="requester",
        planner_profile_id="planner-profile",
        steps=(PlanStep(step_id="step-1", operator=operator, rationale="governed change"),),
    )


def decide(core, request_id: str, signer: str, choice=ApprovalChoice.APPROVE) -> None:
    reason = "reviewed"
    payload = {"request_id": request_id, "choice": choice, "reason": reason}
    core.approvals.decide(
        request_id=request_id,
        choice=choice,
        reason=reason,
        signed_action=core.signers[signer].sign(action="approval_decision", payload=payload),
    )


def test_high_risk_requires_separate_approver(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="high-change",
            description="High risk.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="high-v1",
            risk=RiskLevel.HIGH,
        )
    )
    plan = risk_plan("high-change")
    core.store.record_plan(plan)
    denied = core.verifier.verify(plan)
    assert denied.requires_approval
    request_id = core.verifier.ensure_approval_requests(plan)[0]
    with pytest.raises(AuthorizationError, match="own plan"):
        decide(core, request_id, "requester")
    decide(core, request_id, "approver-1")
    assert core.verifier.verify(plan).allowed


def test_critical_requires_two_distinct_approvers(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="critical-change",
            description="Critical risk.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="critical-v1",
            risk=RiskLevel.CRITICAL,
        )
    )
    plan = risk_plan("critical-change")
    core.store.record_plan(plan)
    request_id = core.verifier.ensure_approval_requests(plan)[0]
    decide(core, request_id, "approver-1")
    assert not core.verifier.verify(plan).allowed
    decide(core, request_id, "approver-2")
    assert core.verifier.verify(plan).allowed


def test_denial_is_terminal_for_plan_revision(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="denied-change",
            description="Denied risk.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="denied-v1",
            risk=RiskLevel.HIGH,
        )
    )
    plan = risk_plan("denied-change")
    core.store.record_plan(plan)
    request_id = core.verifier.ensure_approval_requests(plan)[0]
    decide(core, request_id, "approver-1", ApprovalChoice.DENY)
    result = core.verifier.verify(plan)
    assert not result.allowed
    assert result.findings[0].code == "approval_denied"


def test_approval_is_invalidated_when_approver_grant_is_revoked(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="revoked-change",
            description="High risk.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="revoke-v1",
            risk=RiskLevel.HIGH,
        )
    )
    plan = risk_plan("revoked-change")
    core.store.record_plan(plan)
    request_id = core.verifier.ensure_approval_requests(plan)[0]
    decide(core, request_id, "approver-1")
    assert core.verifier.verify(plan).allowed
    core.store.revoke_approval_grant("approve-approver-1")
    assert not core.verifier.verify(plan).allowed
