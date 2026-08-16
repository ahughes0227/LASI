"""Strict, domain-neutral contracts for semantic state and predicates."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from services.contracts.models import StrictModel

DomainScalar = str | int | float | bool | None


class DomainFact(StrictModel):
    fact_id: str
    project_id: str
    subject: str
    predicate: str
    value: DomainScalar
    status: Literal["observed", "inferred", "verified", "conflicting", "invalidated"]
    confidence: float = Field(ge=0, le=1)
    authority: int = Field(default=0, ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list)
    source: str
    observed_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_semantics(self) -> "DomainFact":
        for field_name in ("project_id", "subject", "predicate", "source"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must be non-empty")
        if self.status in {"observed", "inferred", "verified"} and not self.evidence_refs:
            raise ValueError(f"{self.status} facts require at least one evidence_ref")
        if self.status == "verified" and self.confidence < 0.8:
            raise ValueError("verified facts require confidence >= 0.8")
        return self


class PredicateOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN_SET = "in_set"


class DomainPredicate(StrictModel):
    subject: str
    predicate: str
    operator: PredicateOperator
    value: DomainScalar | list[DomainScalar] = None
    minimum_confidence: float = Field(default=0, ge=0, le=1)
    minimum_authority: int = Field(default=0, ge=0, le=100)
    allowed_statuses: list[str] = Field(
        default_factory=lambda: ["observed", "inferred", "verified"]
    )

    @model_validator(mode="after")
    def validate_operator_value(self) -> "DomainPredicate":
        operator = PredicateOperator(self.operator)
        if operator in {PredicateOperator.EXISTS, PredicateOperator.NOT_EXISTS}:
            if self.value is not None:
                raise ValueError(f"{operator} predicates require value=None")
        elif operator is PredicateOperator.IN_SET:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("in_set predicates require a non-empty list")
        elif self.value is None or isinstance(self.value, list):
            raise ValueError(f"{operator} predicates require a non-None scalar value")
        return self


class PredicateResult(StrictModel):
    predicate: DomainPredicate
    satisfied: bool
    matching_fact_ids: list[str]
    rejected_fact_ids: list[str]
    reason: str


class DomainEffect(StrictModel):
    operation: Literal["assert", "invalidate"]
    subject: str
    predicate: str
    value: DomainScalar = None
    status: Literal["observed", "inferred", "verified"] = "inferred"
    confidence: float = Field(default=1, ge=0, le=1)
    authority: int = Field(default=0, ge=0, le=100)


class DomainStateSnapshot(StrictModel):
    project_id: str
    revision: int = Field(ge=1)
    facts: list[DomainFact]
    created_at: datetime

    @model_validator(mode="after")
    def validate_facts(self) -> "DomainStateSnapshot":
        if any(fact.project_id != self.project_id for fact in self.facts):
            raise ValueError("every fact must have the same project_id as the snapshot")
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("fact_id values must be unique")
        return self

    def active_facts(self, subject: str, predicate: str) -> tuple[DomainFact, ...]:
        now = datetime.now(tz=self.created_at.tzinfo)
        return tuple(
            fact
            for fact in self.facts
            if fact.subject == subject
            and fact.predicate == predicate
            and fact.status not in {"invalidated", "conflicting"}
            and (fact.expires_at is None or fact.expires_at > now)
        )

    def with_facts(self, facts: list[DomainFact], *, revision: int) -> "DomainStateSnapshot":
        return DomainStateSnapshot(
            project_id=self.project_id,
            revision=revision,
            facts=facts,
            created_at=self.created_at,
        )
