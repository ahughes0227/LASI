"""Governed promotion from project ICM to system learned principles."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from services.contracts import ApprovalRecord

from .models import EvidenceStatus, PromotionProposal
from .store import ICMStore


class PromotionService:
    """Creates promotion proposals and writes system context only after approval."""

    def __init__(self, store: ICMStore) -> None:
        self.store = store

    def propose(self, proposal: PromotionProposal) -> Path:
        self._validate_eligibility(proposal)
        path = self.store._safe_project_path(
            proposal.project_id, f"30_evidence/promotions/{proposal.proposal_id}.yaml"
        )
        if path.exists():
            raise FileExistsError(f"promotion proposal already exists: {proposal.proposal_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(proposal.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        return path

    def approve(self, project_id: str, proposal_id: str, approval: ApprovalRecord) -> Path:
        if approval.project_id != project_id:
            raise PermissionError("promotion approval belongs to another project")
        if approval.action_type != "promote_project_lesson":
            raise PermissionError("approval is not authorized for project lesson promotion")
        if approval.approval_status != "approved" or not approval.approved_by:
            raise PermissionError("system ICM promotion requires an explicit human approval")
        path = self.store._safe_project_path(
            project_id, f"30_evidence/promotions/{proposal_id}.yaml"
        )
        proposal = PromotionProposal.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        self._validate_eligibility(proposal)
        principle_path = (
            self.store.system_root / "learned_principles" / f"{proposal.proposal_id}.md"
        )
        if principle_path.exists():
            raise FileExistsError(f"system principle already exists: {proposal.proposal_id}")
        principle_path.parent.mkdir(parents=True, exist_ok=True)
        principle_path.write_text(
            "\n".join(
                [
                    f"# {proposal.title}",
                    "",
                    proposal.principle,
                    "",
                    f"Source projects: {', '.join(proposal.source_projects or [project_id])}",
                    f"Evidence: {', '.join(proposal.evidence_references)}",
                    f"Approved by: {approval.approved_by}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        proposal.status = "approved"
        path.write_text(
            yaml.safe_dump(proposal.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        return principle_path

    def _validate_eligibility(self, proposal: PromotionProposal) -> None:
        state = self.store.reconstruct_project_state(proposal.project_id)
        claims = {claim.claim_id: claim for claim in state.claims}
        selected = [
            claims[claim_id] for claim_id in proposal.source_claim_ids if claim_id in claims
        ]
        strongly_supported = any(
            claim.status in {EvidenceStatus.SUPPORTED, EvidenceStatus.STRONGLY_SUPPORTED}
            for claim in selected
        )
        repeated = len(set(proposal.source_projects)) >= 2
        eligible = (
            repeated
            or strongly_supported
            or proposal.broadly_reusable
            or proposal.critic_approved
            or proposal.explicitly_requested
        )
        if not eligible:
            raise ValueError(
                "promotion requires reusable, supported, repeated, reviewed, or explicit evidence"
            )
