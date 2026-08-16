"""Deterministic evaluation of semantic predicates against state snapshots."""

import math
from numbers import Real

from .models import DomainFact, DomainPredicate, DomainStateSnapshot, PredicateOperator, PredicateResult


class PredicateEvaluator:
    def evaluate(
        self,
        predicate: DomainPredicate,
        snapshot: DomainStateSnapshot,
    ) -> PredicateResult:
        operator = PredicateOperator(predicate.operator)
        candidates = snapshot.active_facts(predicate.subject, predicate.predicate)
        rejected: set[str] = set()
        eligible: list[DomainFact] = []
        for fact in candidates:
            if fact.confidence < predicate.minimum_confidence or fact.authority < predicate.minimum_authority:
                rejected.add(fact.fact_id)
            elif fact.status not in predicate.allowed_statuses:
                rejected.add(fact.fact_id)
            else:
                eligible.append(fact)

        matching: list[str] = []
        if operator is PredicateOperator.EXISTS:
            matching = [fact.fact_id for fact in eligible]
            satisfied = bool(eligible)
            reason = "at least one eligible active fact exists" if satisfied else "no eligible active fact exists"
        elif operator is PredicateOperator.NOT_EXISTS:
            satisfied = not eligible
            reason = "no eligible active fact exists" if satisfied else "an eligible active fact exists"
        else:
            for fact in eligible:
                result = self._matches(predicate, fact)
                if result is True:
                    matching.append(fact.fact_id)
                else:
                    rejected.add(fact.fact_id)
            satisfied = bool(matching)
            reason = "at least one active fact satisfies the predicate" if satisfied else "no active fact satisfies the predicate"

        return PredicateResult(
            predicate=predicate,
            satisfied=satisfied,
            matching_fact_ids=sorted(matching),
            rejected_fact_ids=sorted(rejected),
            reason=reason,
        )

    def evaluate_all(
        self,
        predicates: list[DomainPredicate],
        snapshot: DomainStateSnapshot,
    ) -> tuple[PredicateResult, ...]:
        return tuple(self.evaluate(predicate, snapshot) for predicate in predicates)

    @staticmethod
    def _matches(predicate: DomainPredicate, fact: DomainFact) -> bool:
        operator = PredicateOperator(predicate.operator)
        value = fact.value
        target = predicate.value
        if operator is PredicateOperator.EQUALS:
            return value == target
        if operator is PredicateOperator.NOT_EQUALS:
            return value != target
        if operator is PredicateOperator.IN_SET:
            return value in target  # type: ignore[operator]
        if operator in {
            PredicateOperator.GREATER_THAN_OR_EQUAL,
            PredicateOperator.LESS_THAN_OR_EQUAL,
        }:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
                return False
            if isinstance(target, bool) or not isinstance(target, Real) or not math.isfinite(float(target)):
                return False
            if operator is PredicateOperator.GREATER_THAN_OR_EQUAL:
                return value >= target
            return value <= target
        raise ValueError(f"unsupported operator: {operator}")
