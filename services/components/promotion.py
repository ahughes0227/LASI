"""Governed component promotion; generated code never promotes itself."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from services.contracts import ApprovalRecord, ComponentSpec

from .registry import ComponentHandler, ComponentRegistry


@dataclass(frozen=True)
class ComponentPromotionProposal:
    proposal_id: str
    project_id: str
    component: ComponentSpec
    source_experiment_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    dependency_review_ref: str
    code_review_ref: str


class ComponentPromotionService:
    """Promote reviewed code only after explicit toolbox-change approval."""

    @staticmethod
    def approve_and_register(
        proposal: ComponentPromotionProposal,
        approval: ApprovalRecord,
        registry: ComponentRegistry,
        config_model: type[BaseModel],
        handler: ComponentHandler,
    ) -> ComponentSpec:
        if approval.project_id != proposal.project_id:
            raise PermissionError("component approval belongs to another project")
        if approval.action_type != "update_toolbox":
            raise PermissionError("component promotion requires update_toolbox approval")
        if approval.approval_status != "approved" or not approval.approved_by:
            raise PermissionError("component promotion requires explicit human approval")
        if (
            not proposal.source_experiment_ids
            or not proposal.evidence_refs
            or not proposal.test_refs
        ):
            raise ValueError("component promotion requires experiment evidence and tests")
        if not proposal.dependency_review_ref or not proposal.code_review_ref:
            raise ValueError("component promotion requires dependency and code review references")
        approved = proposal.component.model_copy(update={"lifecycle": "approved"})
        # The explicit handler and config-model arguments keep code loading outside proposal data.
        registry.register(approved, config_model, handler)
        return registry.describe(approved.component_id, approved.version)
