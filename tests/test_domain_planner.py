"""Tests for deterministic backward planning over domain state."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from services.capabilities import CapabilityRegistry
from services.contracts import CapabilitySpec
from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainFact,
    DomainPolicy,
    DomainPolicyEvaluator,
    DomainPolicyRegistry,
    DomainStateSnapshot,
)
from services.planner import DomainGoal, DomainStatePlanner

NOW = datetime.now(UTC)


def _capability(capability_id: str) -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=capability_id, name=capability_id, version="1.0.0",
        purpose="test", operations=["run"], lifecycle="approved",
    )


def _setup(*contracts: CapabilityDomainContract, policies=()):
    capabilities = CapabilityRegistry()
    for contract in contracts:
        capabilities.add(_capability(contract.capability_id))
    domain = CapabilityDomainRegistry.from_items(capabilities, list(contracts))
    policy = DomainPolicyEvaluator(DomainPolicyRegistry.from_items(list(policies)))
    return DomainStatePlanner(domain, policy)


def _contract(capability_id, *, preconditions=(), effects=(), side_effect_class="read", validations=()):
    return CapabilityDomainContract(
        capability_id=capability_id, capability_version="1.0.0",
        preconditions=list(preconditions), effects=list(effects),
        side_effect_class=side_effect_class, validation_capability_ids=list(validations),
        provenance_refs=["test"],
    )


def _predicate(predicate, value=True, operator="equals"):
    return {"subject": "project", "predicate": predicate, "operator": operator, "value": value}


def _effect(predicate, value=True, operation="assert", status="inferred"):
    return {"operation": operation, "subject": "project", "predicate": predicate,
            "value": value, "status": status}


def _snapshot(*facts):
    return DomainStateSnapshot(project_id="project-1", revision=4, facts=list(facts), created_at=NOW)


def _fact(predicate, value=True):
    return DomainFact(
        fact_id=f"fact-{predicate}", project_id="project-1", subject="project",
        predicate=predicate, value=value, status="observed", confidence=1,
        evidence_refs=["test"], source="test", observed_at=NOW,
    )


def _goal(*predicates, **kwargs):
    return DomainGoal(goal_id="goal-1", project_id="project-1", description="test",
                      desired_state=[_predicate(*item) if isinstance(item, tuple) else item for item in predicates], **kwargs)


def test_already_satisfied_goal_returns_no_steps():
    goal = _goal(("ready", True))
    plan = _setup().plan(goal, _snapshot(_fact("ready")))
    assert plan.status == "satisfied"
    assert plan.steps == []
    assert plan.initially_satisfied_predicate_indexes == [0]


def test_planner_selects_capability_whose_effect_satisfies_goal():
    planner = _setup(_contract("make-ready", effects=[_effect("ready")]))
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert plan.status == "planned"
    assert [step.capability_id for step in plan.steps] == ["make-ready"]


def test_planner_inserts_capability_for_missing_precondition():
    planner = _setup(
        _contract("prepare", effects=[_effect("prepared")]),
        _contract("make-ready", preconditions=[_predicate("prepared")], effects=[_effect("ready")]),
    )
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert [step.capability_id for step in plan.steps] == ["prepare", "make-ready"]


def test_planner_inserts_validation_after_mutating_step():
    planner = _setup(
        _contract("validate", effects=[_effect("validated")]),
        _contract("update", effects=[_effect("ready")], side_effect_class="update", validations=["validate"]),
    )
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert [step.capability_id for step in plan.steps] == ["update", "validate"]


def test_read_only_goal_rejects_mutating_capability():
    planner = _setup(_contract("validate"),
                     _contract("update", effects=[_effect("ready")], side_effect_class="update", validations=["validate"]),
                     _contract("read", effects=[_effect("ready")], side_effect_class="read"))
    plan = planner.plan(_goal(("ready", True), forbidden_side_effects=["update"]), _snapshot())
    assert [step.capability_id for step in plan.steps] == ["read"]
    assert any(item.capability_id == "update" for item in plan.rejected_capabilities)


def test_blocking_policy_rejects_capability():
    policy = DomainPolicy(policy_id="block", version="1", status="approved", scope="project",
                          action="use_capability:update", priority=1, when=[], outcome="block",
                          reason="blocked", provenance_refs=["test"])
    planner = _setup(_contract("update", effects=[_effect("ready")]), policies=[policy])
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert plan.status == "blocked"
    assert plan.rejected_capabilities[0].policy_outcome == "block"


def test_approval_policy_is_preserved_in_plan():
    policy = DomainPolicy(policy_id="approve", version="1", status="approved", scope="project",
                          action="use_capability:update", priority=1, when=[], outcome="require_approval",
                          reason="review", required_approval_action="change", provenance_refs=["test"])
    planner = _setup(_contract("update", effects=[_effect("ready")]), policies=[policy])
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert plan.status == "planned"
    assert plan.policy_decisions[0].outcome == "require_approval"


def test_planner_uses_deterministic_tie_breaking():
    planner = _setup(_contract("z-read", effects=[_effect("ready")]), _contract("a-read", effects=[_effect("ready")]))
    plan = planner.plan(_goal(("ready", True)), _snapshot())
    assert [step.capability_id for step in plan.steps] == ["a-read"]


def test_planner_returns_blocked_for_unreachable_predicate():
    plan = _setup().plan(_goal(("missing", True)), _snapshot())
    assert plan.status == "blocked"
    assert plan.unresolved_predicate_indexes == [0]


def test_planner_stops_at_maximum_steps():
    planner = _setup(_contract("prepare", effects=[_effect("prepared")]),
                     _contract("ready", preconditions=[_predicate("prepared")], effects=[_effect("ready")]))
    plan = planner.plan(_goal(("ready", True), maximum_steps=1), _snapshot())
    assert plan.status == "incomplete"


def test_planner_does_not_mutate_snapshot():
    planner = _setup(_contract("make-ready", effects=[_effect("ready")]))
    snapshot = _snapshot()
    before = deepcopy(snapshot.model_dump())
    planner.plan(_goal(("ready", True)), snapshot)
    assert snapshot.model_dump() == before


def test_planner_rejects_cross_project_goal():
    planner = _setup()
    with pytest.raises(ValueError, match="project_id"):
        planner.plan(DomainGoal(goal_id="goal", project_id="other", description="x",
                                desired_state=[_predicate("ready")]), _snapshot())
