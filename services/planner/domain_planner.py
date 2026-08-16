"""Deterministic backward planner for semantic domain capabilities."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainEffect,
    DomainFact,
    DomainPolicyDecision,
    DomainPolicyEvaluator,
    DomainPredicate,
    DomainStateSnapshot,
    PredicateEvaluator,
    PredicateOperator,
)

from .domain_models import (
    DomainGoal,
    DomainPlan,
    PlannedCapabilityStep,
    RejectedCapability,
)

_SIDE_EFFECT_RANK = {"none": 0, "read": 1, "create": 2, "update": 3, "delete": 4, "external": 5}


@dataclass(frozen=True)
class _SearchResult:
    steps: tuple[PlannedCapabilityStep, ...]
    snapshot: DomainStateSnapshot
    decisions: tuple[DomainPolicyDecision, ...]
    rejected: tuple[RejectedCapability, ...]
    rationale: tuple[str, ...]
    complete: bool
    blocked: bool


class DomainStatePlanner:
    """Plan a shortest policy-compliant capability sequence without executing it."""

    def __init__(
        self,
        capabilities: CapabilityDomainRegistry,
        policies: DomainPolicyEvaluator,
    ) -> None:
        self.capabilities = capabilities
        self.policies = policies
        self.predicates = PredicateEvaluator()

    def plan(self, goal: DomainGoal, snapshot: DomainStateSnapshot) -> DomainPlan:
        if goal.project_id != snapshot.project_id:
            raise ValueError("goal project_id must match snapshot project_id")

        initial = self.predicates.evaluate_all(goal.desired_state, snapshot)
        initially_satisfied = [i for i, result in enumerate(initial) if result.satisfied]
        unresolved = [i for i, result in enumerate(initial) if not result.satisfied]
        if not unresolved:
            return self._make_plan(
                goal,
                snapshot,
                "satisfied",
                (),
                initially_satisfied,
                [],
                (),
                (),
                ["All desired predicates are already satisfied."],
            )

        result = self._search(goal, snapshot)
        status: Literal["planned", "blocked", "incomplete"] = (
            "planned" if result.complete else "blocked" if result.blocked else "incomplete"
        )
        final_results = self.predicates.evaluate_all(goal.desired_state, result.snapshot)
        unresolved = [i for i, item in enumerate(final_results) if not item.satisfied]
        rationale = list(result.rationale)
        if status == "blocked":
            rationale.append(
                "No policy-compliant capability sequence can satisfy the unresolved predicates."
            )
        elif status == "incomplete":
            rationale.append(f"Maximum step limit reached ({goal.maximum_steps}).")
        return self._make_plan(
            goal,
            snapshot,
            status,
            result.steps,
            initially_satisfied,
            unresolved,
            result.decisions,
            result.rejected,
            rationale,
        )

    def _search(self, goal: DomainGoal, snapshot: DomainStateSnapshot) -> _SearchResult:
        """Breadth-first search; queue order is deterministic and candidates are sorted."""
        queue = deque([_SearchResult((), snapshot, (), (), (), False, False)])
        best_incomplete: _SearchResult | None = None
        complete_results: list[_SearchResult] = []
        complete_depth: int | None = None
        rejected_pool: list[RejectedCapability] = []
        seen: set[tuple[tuple[tuple[str, str, str, str], ...], tuple[str, ...]]] = set()
        while queue:
            state = queue.popleft()
            results = self.predicates.evaluate_all(goal.desired_state, state.snapshot)
            unresolved = [i for i, item in enumerate(results) if not item.satisfied]
            if not unresolved:
                if complete_depth is None:
                    complete_depth = len(state.steps)
                if len(state.steps) == complete_depth:
                    complete_results.append(state.__class__(**{**state.__dict__, "complete": True}))
                continue
            if complete_depth is not None and len(state.steps) >= complete_depth:
                continue
            if len(state.steps) >= goal.maximum_steps:
                best_incomplete = state
                continue
            target_index = unresolved[0]
            target = goal.desired_state[target_index]
            candidates = self._candidates(target)
            expanded = False
            for contract in candidates:
                decision = self.policies.evaluate(
                    f"use_capability:{contract.capability_id}", state.snapshot
                )
                rejection = self._rejection(goal, contract, decision)
                if rejection:
                    rejected_pool.append(rejection)
                    continue

                if any(
                    step.capability_id == contract.capability_id for step in state.steps
                ) and all(
                    self._effect_established(effect, state.snapshot) for effect in contract.effects
                ):
                    continue

                pre = self._ensure_predicates(
                    goal, contract.preconditions, state.snapshot, state.steps
                )
                if pre is None:
                    rejection = RejectedCapability(
                        capability_id=contract.capability_id,
                        reason="Required preconditions are unreachable.",
                        failed_preconditions=list(contract.preconditions),
                    )
                    rejected_pool.append(rejection)
                    continue
                pre_snapshot, pre_steps, pre_decisions, pre_rejected, pre_rationale = pre
                added_steps = list(pre_steps)
                if len(state.steps) + len(added_steps) + 1 > goal.maximum_steps:
                    best_incomplete = state
                    continue
                simulated = self._simulate(pre_snapshot, contract, goal.goal_id)
                satisfies = [
                    i
                    for i, predicate in enumerate(goal.desired_state)
                    if self.predicates.evaluate(predicate, simulated).satisfied
                ]
                if target_index not in satisfies:
                    continue
                step = self._step(contract, satisfies)
                added_steps.append(step)
                decisions = self._append_decision((*state.decisions, *pre_decisions), decision)
                rejected = self._merge_rejections(state.rejected, pre_rejected)
                rationale = (
                    *state.rationale,
                    *pre_rationale,
                    f"Selected {contract.capability_id} to satisfy predicate index {target_index}.",
                )
                post = simulated
                for validation_id in contract.validation_capability_ids:
                    validation = self.capabilities.get(validation_id)
                    validation_decision = self.policies.evaluate(
                        f"use_capability:{validation_id}", post
                    )
                    if validation_decision.outcome == "block":
                        added_steps = []
                        break
                    if len(state.steps) + len(added_steps) + 1 > goal.maximum_steps:
                        added_steps = []
                        best_incomplete = state
                        break
                    added_steps.append(self._step(validation, []))
                    decisions = self._append_decision(decisions, validation_decision)
                    post = self._simulate(post, validation, goal.goal_id)
                if not added_steps:
                    continue
                signature = (
                    self._snapshot_signature(post),
                    tuple(step.capability_id for step in added_steps),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                expanded = True
                queue.append(
                    _SearchResult(
                        (*state.steps, *added_steps),
                        post,
                        decisions,
                        rejected,
                        rationale,
                        False,
                        False,
                    )
                )
            if not expanded and candidates:
                best_incomplete = best_incomplete or _SearchResult(
                    state.steps,
                    state.snapshot,
                    state.decisions,
                    state.rejected,
                    state.rationale,
                    False,
                    True,
                )
        if complete_results:
            winner = min(complete_results, key=self._result_key)
            return _SearchResult(
                winner.steps,
                winner.snapshot,
                winner.decisions,
                self._merge_rejections(winner.rejected, tuple(rejected_pool)),
                winner.rationale,
                True,
                False,
            )
        if best_incomplete:
            return _SearchResult(
                best_incomplete.steps,
                best_incomplete.snapshot,
                best_incomplete.decisions,
                self._merge_rejections(best_incomplete.rejected, tuple(rejected_pool)),
                best_incomplete.rationale,
                False,
                best_incomplete.blocked,
            )
        return _SearchResult((), snapshot, (), tuple(rejected_pool), (), False, True)

    def _ensure_predicates(
        self,
        goal: DomainGoal,
        predicates: list[DomainPredicate],
        snapshot: DomainStateSnapshot,
        existing_steps: tuple[PlannedCapabilityStep, ...],
    ) -> (
        tuple[
            DomainStateSnapshot,
            tuple[PlannedCapabilityStep, ...],
            tuple[DomainPolicyDecision, ...],
            tuple[RejectedCapability, ...],
            tuple[str, ...],
        ]
        | None
    ):
        if not predicates:
            return snapshot, (), (), (), ()
        results = self.predicates.evaluate_all(list(predicates), snapshot)
        if all(item.satisfied for item in results):
            return snapshot, (), (), (), ()
        subgoal = DomainGoal(
            goal_id=f"{goal.goal_id}:preconditions",
            project_id=goal.project_id,
            description="Capability preconditions",
            desired_state=list(predicates),
            forbidden_side_effects=goal.forbidden_side_effects,
            maximum_steps=max(1, goal.maximum_steps - len(existing_steps)),
        )
        result = self._search(subgoal, snapshot)
        if not result.complete:
            return None
        return result.snapshot, result.steps, result.decisions, result.rejected, result.rationale

    def _candidates(self, target: DomainPredicate) -> list[CapabilityDomainContract]:
        candidates = []
        for contract in self.capabilities.all():
            for effect in contract.effects:
                if effect.subject != target.subject or effect.predicate != target.predicate:
                    continue
                if (
                    PredicateOperator(target.operator) is PredicateOperator.EQUALS
                    and effect.value != target.value
                ):
                    continue
                candidates.append(contract)
                break
        return sorted(candidates, key=lambda item: (self._side_effect(item), item.capability_id))

    @staticmethod
    def _side_effect(contract: CapabilityDomainContract) -> int:
        return _SIDE_EFFECT_RANK[contract.side_effect_class]

    @staticmethod
    def _rejection(
        goal: DomainGoal,
        contract: CapabilityDomainContract,
        decision: DomainPolicyDecision,
    ) -> RejectedCapability | None:
        if contract.side_effect_class in goal.forbidden_side_effects:
            return RejectedCapability(
                capability_id=contract.capability_id,
                reason=(
                    f"Side-effect class {contract.side_effect_class!r} is forbidden by the goal."
                ),
            )
        if decision.outcome == "block":
            return RejectedCapability(
                capability_id=contract.capability_id,
                reason=decision.reason,
                policy_outcome=decision.outcome,
            )
        return None

    def _simulate(
        self,
        snapshot: DomainStateSnapshot,
        contract: CapabilityDomainContract,
        goal_id: str,
    ) -> DomainStateSnapshot:
        facts = list(snapshot.facts)
        now = datetime.now(UTC)
        for effect in contract.effects:
            if effect.operation == "invalidate":
                facts = [
                    fact.model_copy(update={"status": "invalidated"})
                    if fact.subject == effect.subject and fact.predicate == effect.predicate
                    else fact
                    for fact in facts
                ]
            else:
                facts.append(
                    DomainFact(
                        fact_id=f"plan-fact-{uuid4().hex}",
                        project_id=snapshot.project_id,
                        subject=effect.subject,
                        predicate=effect.predicate,
                        value=effect.value,
                        status=effect.status,
                        confidence=effect.confidence,
                        authority=effect.authority,
                        evidence_refs=[
                            f"plan://{goal_id}/{contract.capability_id}/{effect.predicate}"
                        ],
                        source="domain_planner_simulation",
                        observed_at=now,
                    )
                )
        return snapshot.with_facts(facts, revision=snapshot.revision)

    def _effect_established(self, effect: DomainEffect, snapshot: DomainStateSnapshot) -> bool:
        if effect.operation == "invalidate":
            return not snapshot.active_facts(effect.subject, effect.predicate)
        predicate = DomainPredicate(
            subject=effect.subject,
            predicate=effect.predicate,
            operator=PredicateOperator.EQUALS,
            value=effect.value,
            minimum_confidence=effect.confidence,
            minimum_authority=effect.authority,
        )
        return self.predicates.evaluate(predicate, snapshot).satisfied

    @staticmethod
    def _result_key(result: _SearchResult) -> tuple[int, int, int, tuple[str, ...]]:
        return (
            len(result.steps),
            sum(_SIDE_EFFECT_RANK.get(step.side_effect_class, 99) for step in result.steps),
            sum(decision.outcome == "require_approval" for decision in result.decisions),
            tuple(step.capability_id for step in result.steps),
        )

    def _step(
        self, contract: CapabilityDomainContract, indexes: list[int]
    ) -> PlannedCapabilityStep:
        return PlannedCapabilityStep(
            step_id=f"step-{uuid4().hex}",
            capability_id=contract.capability_id,
            satisfies_predicate_indexes=sorted(indexes),
            required_predicates=contract.preconditions,
            expected_effects=contract.effects,
            side_effect_class=contract.side_effect_class,
            validation_capability_ids=contract.validation_capability_ids,
        )

    @staticmethod
    def _snapshot_signature(
        snapshot: DomainStateSnapshot,
    ) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            sorted((f.subject, f.predicate, str(f.value), f.status) for f in snapshot.facts)
        )

    @staticmethod
    def _append_decision(
        items: tuple[DomainPolicyDecision, ...], decision: DomainPolicyDecision
    ) -> tuple[DomainPolicyDecision, ...]:
        return (
            (*items, decision) if decision.action not in {item.action for item in items} else items
        )

    @staticmethod
    def _append_rejection(
        items: tuple[RejectedCapability, ...], rejection: RejectedCapability
    ) -> tuple[RejectedCapability, ...]:
        return (
            (*items, rejection)
            if rejection.capability_id not in {item.capability_id for item in items}
            else items
        )

    @staticmethod
    def _merge_rejections(
        left: tuple[RejectedCapability, ...], right: tuple[RejectedCapability, ...]
    ) -> tuple[RejectedCapability, ...]:
        result = list(left)
        for item in right:
            if item.capability_id not in {entry.capability_id for entry in result}:
                result.append(item)
        return tuple(result)

    @staticmethod
    def _make_plan(
        goal: DomainGoal,
        snapshot: DomainStateSnapshot,
        status: Literal["satisfied", "planned", "blocked", "incomplete"],
        steps: tuple[PlannedCapabilityStep, ...],
        initial: list[int],
        unresolved: list[int],
        decisions: tuple[DomainPolicyDecision, ...],
        rejected: tuple[RejectedCapability, ...],
        rationale: list[str],
    ) -> DomainPlan:
        return DomainPlan(
            plan_id=f"domain-plan-{uuid4().hex}",
            goal=goal,
            observed_revision=snapshot.revision,
            status=status,
            steps=list(steps),
            initially_satisfied_predicate_indexes=list(initial),
            unresolved_predicate_indexes=list(unresolved),
            policy_decisions=list(decisions),
            rejected_capabilities=list(rejected),
            rationale=list(rationale),
        )
