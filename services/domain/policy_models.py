"""Contracts for executable, data-only domain policies."""

from typing import Literal

from pydantic import Field, model_validator

from services.contracts.models import StrictModel

from .models import DomainPredicate


class DomainPolicy(StrictModel):
    policy_id: str
    version: str
    status: Literal["draft", "approved", "retired"]
    scope: Literal["system", "project"]
    action: str
    priority: int = Field(default=0, ge=0, le=1000)
    when: list[DomainPredicate]
    outcome: Literal["allow", "block", "require_approval"]
    reason: str
    required_approval_action: str | None = None
    provenance_refs: list[str]

    @model_validator(mode="after")
    def validate_governance(self) -> "DomainPolicy":
        if self.status == "approved" and not self.provenance_refs:
            raise ValueError("approved policies require at least one provenance_ref")
        if self.outcome == "require_approval" and not self.required_approval_action:
            raise ValueError("require_approval policies require required_approval_action")
        if self.outcome != "require_approval" and self.required_approval_action is not None:
            raise ValueError("required_approval_action is only valid for require_approval policies")
        return self


class DomainPolicyDecision(StrictModel):
    action: str
    outcome: Literal["allow", "block", "require_approval", "not_applicable"]
    applied_policy_ids: list[str]
    failed_predicates: dict[str, list[str]]
    reason: str
