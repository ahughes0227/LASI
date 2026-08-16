"""Tests for deterministic, data-only domain policy evaluation."""

from datetime import UTC, datetime

import pytest
from services.domain import (
    DomainFact,
    DomainPolicy,
    DomainPolicyEvaluator,
    DomainPolicyRegistry,
    DomainStateSnapshot,
)


def _policy(
    policy_id: str,
    *,
    action: str = "read_only_comparison",
    outcome: str = "allow",
    priority: int = 10,
    status: str = "approved",
    when: list[dict] | None = None,
    required: str | None = None,
) -> DomainPolicy:
    return DomainPolicy(
        policy_id=policy_id,
        version="1",
        status=status,
        scope="project",
        action=action,
        priority=priority,
        when=when
        or [
            {
                "subject": "identity",
                "predicate": "verified",
                "operator": "equals",
                "value": True,
            }
        ],
        outcome=outcome,
        reason=f"reason-{policy_id}",
        required_approval_action=required,
        provenance_refs=["evidence:policy-test"] if status == "approved" else [],
    )


def _snapshot(
    *, verified: bool = True, confidence: float = 0.95, authoritative: bool = False
) -> DomainStateSnapshot:
    facts = [
        DomainFact(
            fact_id="fact-1",
            project_id="project-1",
            subject="identity",
            predicate="verified",
            value=verified,
            status="verified",
            confidence=confidence,
            authority=90,
            evidence_refs=["evidence-1"],
            source="test",
            observed_at=datetime.now(UTC),
        )
    ]
    if authoritative:
        facts.append(
            DomainFact(
                fact_id="fact-2",
                project_id="project-1",
                subject="source",
                predicate="authoritative",
                value=True,
                status="verified",
                confidence=0.99,
                authority=100,
                evidence_refs=["evidence-2"],
                source="test",
                observed_at=datetime.now(UTC),
            )
        )
    return DomainStateSnapshot(
        project_id="project-1", revision=1, facts=facts, created_at=datetime.now(UTC)
    )


def test_registry_loads_approved_policy(tmp_path) -> None:
    (tmp_path / "policy.yaml").write_text(
        """policy_id: read
version: '1'
status: approved
scope: project
action: read
priority: 1
when: []
outcome: allow
reason: safe
provenance_refs: [evidence-1]
""",
        encoding="utf-8",
    )
    assert DomainPolicyRegistry(tmp_path).for_action("read")[0].policy_id == "read"


def test_registry_rejects_duplicate_policy_version() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DomainPolicyRegistry.from_items([_policy("same"), _policy("same")])


def test_registry_does_not_return_draft_or_retired_by_default() -> None:
    registry = DomainPolicyRegistry.from_items(
        [_policy("draft", status="draft"), _policy("retired", status="retired")]
    )
    assert registry.all() == ()
    assert registry.for_action("read_only_comparison") == ()


def test_policy_applies_only_when_all_predicates_match() -> None:
    policy = _policy(
        "both",
        when=[
            {"subject": "identity", "predicate": "verified", "operator": "equals", "value": True},
            {
                "subject": "source",
                "predicate": "authoritative",
                "operator": "equals",
                "value": True,
            },
        ],
    )
    decision = DomainPolicyEvaluator(DomainPolicyRegistry.from_items([policy])).evaluate(
        "read_only_comparison", _snapshot()
    )
    assert decision.outcome == "not_applicable"


def test_block_outranks_require_approval_and_allow() -> None:
    policies = [
        _policy("allow", priority=100),
        _policy("approval", outcome="require_approval", required="modify", priority=90),
        _policy("block", outcome="block", priority=1),
    ]
    decision = DomainPolicyEvaluator(DomainPolicyRegistry.from_items(policies)).evaluate(
        "read_only_comparison", _snapshot()
    )
    assert decision.outcome == "block"
    assert decision.applied_policy_ids == ["block"]


def test_require_approval_outranks_allow() -> None:
    policies = [
        _policy("allow", priority=100),
        _policy("approval", outcome="require_approval", required="modify", priority=1),
    ]
    decision = DomainPolicyEvaluator(DomainPolicyRegistry.from_items(policies)).evaluate(
        "read_only_comparison", _snapshot()
    )
    assert decision.outcome == "require_approval"


def test_unknown_action_returns_not_applicable() -> None:
    decision = DomainPolicyEvaluator(DomainPolicyRegistry.from_items([])).evaluate(
        "unknown", _snapshot()
    )
    assert decision.outcome == "not_applicable"


def test_decision_records_failed_predicate_reasons() -> None:
    policy = _policy(
        "verified",
        when=[
            {
                "subject": "identity",
                "predicate": "verified",
                "operator": "equals",
                "value": True,
            }
        ],
    )
    decision = DomainPolicyEvaluator(DomainPolicyRegistry.from_items([policy])).evaluate(
        "read_only_comparison", _snapshot(verified=False)
    )
    assert decision.failed_predicates["verified"]
