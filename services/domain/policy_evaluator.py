"""Deterministic evaluation of approved domain policies."""

from typing import Literal, cast

from .models import DomainStateSnapshot
from .policy_models import DomainPolicyDecision
from .policy_registry import DomainPolicyRegistry
from .predicates import PredicateEvaluator


class DomainPolicyEvaluator:
    def __init__(self, registry: DomainPolicyRegistry):
        self._registry = registry
        self._predicates = PredicateEvaluator()

    def evaluate(self, action: str, snapshot: DomainStateSnapshot) -> DomainPolicyDecision:
        applied: dict[str, list[str]] = {}
        failed: dict[str, list[str]] = {}
        policies = self._registry.for_action(action)
        for policy in policies:
            results = self._predicates.evaluate_all(policy.when, snapshot)
            reasons = [result.reason for result in results if not result.satisfied]
            if reasons:
                failed[policy.policy_id] = reasons
            else:
                applied[policy.policy_id] = []

        if not applied:
            return DomainPolicyDecision(
                action=action,
                outcome="not_applicable",
                applied_policy_ids=[],
                failed_predicates=failed,
                reason=(
                    "No approved domain policy applies."
                    if policies
                    else "No approved policy exists for this action."
                ),
            )

        policies_by_id = {policy.policy_id: policy for policy in policies}
        ordered_ids = [policy.policy_id for policy in policies if policy.policy_id in applied]
        outcome = cast(
            Literal["block", "require_approval", "allow"],
            next(
                outcome
                for outcome in ("block", "require_approval", "allow")
                if any(policies_by_id[policy_id].outcome == outcome for policy_id in ordered_ids)
            ),
        )
        selected = [
            policy_id for policy_id in ordered_ids if policies_by_id[policy_id].outcome == outcome
        ]
        reasons = [policies_by_id[policy_id].reason for policy_id in selected]
        return DomainPolicyDecision(
            action=action,
            outcome=outcome,
            applied_policy_ids=selected,
            failed_predicates=failed,
            reason=" ".join(reasons),
        )
