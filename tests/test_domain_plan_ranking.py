"""Selection among admissible plans, and the boundary it must not cross.

Search decides which plans are admissible; the ranker decides which admissible plan is
preferred.  These tests pin that split: a ranker may change the choice, and may never
change the set it chooses from (ADR-002).
"""

from datetime import UTC, datetime

import pytest
from services.capabilities import CapabilityRegistry
from services.contracts import CapabilitySpec
from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainPolicyEvaluator,
    DomainPolicyRegistry,
    DomainStateSnapshot,
)
from services.planner import (
    MAX_RETAINED_ALTERNATIVES,
    DomainGoal,
    DomainStatePlanner,
    LexicographicPlanRanker,
    PlanCandidate,
    RankingContractError,
)

NOW = datetime.now(UTC)


def _capability(capability_id: str) -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=capability_id,
        name=capability_id,
        version="1.0.0",
        purpose="test",
        operations=["run"],
        lifecycle="approved",
    )


def _contract(capability_id: str, *, side_effect_class: str = "read") -> CapabilityDomainContract:
    """A capability that single-handedly satisfies the `ready` goal."""
    return CapabilityDomainContract(
        capability_id=capability_id,
        capability_version="1.0.0",
        preconditions=[],
        effects=[
            {
                "operation": "assert",
                "subject": "project",
                "predicate": "ready",
                "value": True,
                "status": "inferred",
            }
        ],
        side_effect_class=side_effect_class,
        validation_capability_ids=[],
        provenance_refs=["test"],
    )


def _planner(*contracts: CapabilityDomainContract, ranker=None) -> DomainStatePlanner:
    capabilities = CapabilityRegistry()
    for contract in contracts:
        capabilities.add(_capability(contract.capability_id))
    domain = CapabilityDomainRegistry.from_items(capabilities, list(contracts))
    policy = DomainPolicyEvaluator(DomainPolicyRegistry.from_items([]))
    return DomainStatePlanner(domain, policy, ranker)


def _goal() -> DomainGoal:
    return DomainGoal(
        goal_id="goal-1",
        project_id="project-1",
        description="test",
        desired_state=[
            {"subject": "project", "predicate": "ready", "operator": "equals", "value": True}
        ],
    )


def _snapshot() -> DomainStateSnapshot:
    return DomainStateSnapshot(project_id="project-1", revision=4, facts=[], created_at=NOW)


class _ReversingRanker:
    """Chooses what the default ranker would have chosen last."""

    ranker_id = "reversing"
    ranker_version = "9.9"

    def rank(self, candidates, *, goal):
        return tuple(sorted(candidates, key=LexicographicPlanRanker.sort_key, reverse=True))


class _DroppingRanker:
    ranker_id = "dropping"
    ranker_version = "1.0"

    def rank(self, candidates, *, goal):
        return tuple(candidates[:1])


class _SmugglingRanker:
    """Attempts to introduce a plan search never found admissible."""

    ranker_id = "smuggling"
    ranker_version = "1.0"

    def rank(self, candidates, *, goal):
        forged = PlanCandidate(candidate_id="forged", steps=(), decisions=())
        return (forged, *candidates)


def test_admissible_plans_the_ranker_rejected_are_retained():
    plan = _planner(_contract("alpha"), _contract("beta")).plan(_goal(), _snapshot())

    assert plan.status == "planned"
    assert [step.capability_id for step in plan.steps] == ["alpha"]
    # Without the losing plan on the record, nothing downstream can tell that a choice
    # was made at all, let alone learn from it.
    assert [alternative.capability_ids for alternative in plan.considered_alternatives] == [
        ["beta"]
    ]
    assert plan.considered_alternatives[0].rank == 2


def test_single_admissible_plan_has_no_alternatives():
    plan = _planner(_contract("alpha")).plan(_goal(), _snapshot())

    assert [step.capability_id for step in plan.steps] == ["alpha"]
    assert plan.considered_alternatives == []


def test_default_ranker_still_prefers_the_lighter_side_effect():
    plan = _planner(
        _contract("alpha", side_effect_class="create"), _contract("beta", side_effect_class="read")
    ).plan(_goal(), _snapshot())

    assert [step.capability_id for step in plan.steps] == ["beta"]
    assert plan.considered_alternatives[0].capability_ids == ["alpha"]
    assert plan.considered_alternatives[0].side_effect_score > 0


def test_plan_records_which_ranker_selected_it():
    plan = _planner(_contract("alpha")).plan(_goal(), _snapshot())

    assert (plan.ranker_id, plan.ranker_version) == ("lexicographic", "1.0")


def test_a_different_ranker_changes_the_choice_but_not_the_candidates():
    contracts = (_contract("alpha"), _contract("beta"))
    default = _planner(*contracts).plan(_goal(), _snapshot())
    reversed_ = _planner(*contracts, ranker=_ReversingRanker()).plan(_goal(), _snapshot())

    assert [step.capability_id for step in default.steps] == ["alpha"]
    assert [step.capability_id for step in reversed_.steps] == ["beta"]
    assert reversed_.ranker_id == "reversing"

    # The same two plans were available to both; only the preference differed.
    def considered(plan):
        return {tuple(step.capability_id for step in plan.steps)} | {
            tuple(alternative.capability_ids) for alternative in plan.considered_alternatives
        }

    assert considered(default) == considered(reversed_) == {("alpha",), ("beta",)}


def test_alternatives_are_bounded():
    contracts = [_contract(f"cap-{index:02d}") for index in range(MAX_RETAINED_ALTERNATIVES + 4)]
    plan = _planner(*contracts).plan(_goal(), _snapshot())

    assert len(plan.considered_alternatives) == MAX_RETAINED_ALTERNATIVES
    assert [alternative.rank for alternative in plan.considered_alternatives] == list(
        range(2, MAX_RETAINED_ALTERNATIVES + 2)
    )


def test_satisfied_goal_records_no_alternatives():
    snapshot = DomainStateSnapshot(
        project_id="project-1",
        revision=4,
        facts=[
            {
                "fact_id": "fact-ready",
                "project_id": "project-1",
                "subject": "project",
                "predicate": "ready",
                "value": True,
                "status": "observed",
                "confidence": 1,
                "evidence_refs": ["test"],
                "source": "test",
                "observed_at": NOW,
            }
        ],
        created_at=NOW,
    )
    plan = _planner(_contract("alpha")).plan(_goal(), snapshot)

    assert plan.status == "satisfied"
    assert plan.considered_alternatives == []


def test_a_ranker_cannot_drop_a_candidate():
    planner = _planner(_contract("alpha"), _contract("beta"), ranker=_DroppingRanker())

    with pytest.raises(RankingContractError):
        planner.plan(_goal(), _snapshot())


def test_a_ranker_cannot_introduce_a_plan_search_did_not_admit():
    """The ADR-002 invariant: selection may reorder, never widen."""
    planner = _planner(_contract("alpha"), _contract("beta"), ranker=_SmugglingRanker())

    with pytest.raises(RankingContractError):
        planner.plan(_goal(), _snapshot())
