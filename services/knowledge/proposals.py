"""Proposal-only knowledge curation with explicit approval boundaries."""

from services.contracts import KnowledgeProposal

_HIGH_CONSEQUENCE = {
    "fact",
    "policy",
    "new_fact",
    "new_policy",
    "policy_update",
    "hypothesis_promotion",
    "hypothesis_retirement",
    "lesson",
    "new_lesson",
    "lesson_retirement",
    "contradiction_warning",
    "new_literature_summary",
    "new_taxonomy_entry",
    "new_template",
    "new_toolbox_note",
    "obsolete_knowledge_warning",
}
_PROPOSAL_TYPES = _HIGH_CONSEQUENCE | {
    "hypothesis",
    "lesson",
    "new_hypothesis",
    "new_lesson",
    "new_literature_summary",
    "new_toolbox_note",
    "new_taxonomy_entry",
    "new_template",
    "hypothesis_retirement",
    "lesson_retirement",
    "contradiction_warning",
    "obsolete_knowledge_warning",
}


def proposal_requires_human_approval(proposal_type: str) -> bool:
    """Return whether governance requires an explicit human approval record."""
    return proposal_type in _HIGH_CONSEQUENCE


def validate_proposal(proposal: KnowledgeProposal) -> KnowledgeProposal:
    """Validate proposal type and prevent silent high-consequence approval."""
    if proposal.proposal_type not in _PROPOSAL_TYPES:
        raise ValueError(f"unsupported knowledge proposal type: {proposal.proposal_type}")
    if proposal_requires_human_approval(proposal.proposal_type) and proposal.status in {
        "approved",
        "implemented",
    }:
        raise ValueError("governed knowledge transitions require human approval")
    if proposal_requires_human_approval(proposal.proposal_type) and not proposal.approval_required:
        raise ValueError("high-consequence knowledge proposals must require approval")
    return proposal


class KnowledgeCurator:
    """Draft proposals; this service intentionally has no approval operation."""

    def propose(self, proposal: KnowledgeProposal) -> KnowledgeProposal:
        return validate_proposal(proposal)
