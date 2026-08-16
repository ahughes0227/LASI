"""Contracts for deterministic planning over semantic domain state."""

from typing import Literal

from pydantic import Field

from services.contracts.models import StrictModel
from services.domain.models import DomainEffect, DomainPredicate
from services.domain.policy_models import DomainPolicyDecision


class DomainGoal(StrictModel):
    goal_id: str
    project_id: str
    description: str
    desired_state: list[DomainPredicate] = Field(min_length=1)
    forbidden_side_effects: list[str] = Field(default_factory=list)
    maximum_steps: int = Field(default=12, ge=1, le=50)


class PlannedCapabilityStep(StrictModel):
    step_id: str
    capability_id: str
    satisfies_predicate_indexes: list[int] = Field(default_factory=list)
    required_predicates: list[DomainPredicate] = Field(default_factory=list)
    expected_effects: list[DomainEffect] = Field(default_factory=list)
    side_effect_class: str
    validation_capability_ids: list[str] = Field(default_factory=list)


class RejectedCapability(StrictModel):
    capability_id: str
    reason: str
    failed_preconditions: list[DomainPredicate] = Field(default_factory=list)
    policy_outcome: str | None = None


class DomainPlan(StrictModel):
    plan_id: str
    goal: DomainGoal
    observed_revision: int
    status: Literal["satisfied", "planned", "blocked", "incomplete"]
    steps: list[PlannedCapabilityStep] = Field(default_factory=list)
    initially_satisfied_predicate_indexes: list[int] = Field(default_factory=list)
    unresolved_predicate_indexes: list[int] = Field(default_factory=list)
    policy_decisions: list[DomainPolicyDecision] = Field(default_factory=list)
    rejected_capabilities: list[RejectedCapability] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
