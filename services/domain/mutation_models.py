"""Contracts for governed mutation of derived artifacts."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from services.contracts.models import StrictModel

from .models import DomainPredicate, PredicateResult


class MutationPreview(StrictModel):
    mutation_id: str
    project_id: str
    action: str
    source_ref: str
    source_hash: str
    derived_ref: str
    changes: list[str] = Field(min_length=1)
    required_preconditions: list[DomainPredicate]
    expected_postconditions: list[DomainPredicate]
    compensation_action: str | None
    created_at: datetime


class MutationAuthorization(StrictModel):
    mutation_id: str
    decision_id: str
    approval_id: str | None
    allowed: bool
    conditions: list[str]


class MutationResult(StrictModel):
    mutation_id: str
    status: Literal["applied", "blocked", "failed", "compensated", "quarantined"]
    output_ref: str | None
    output_hash: str | None
    validation_results: list[PredicateResult]
    errors: list[str]
    compensation_ref: str | None
