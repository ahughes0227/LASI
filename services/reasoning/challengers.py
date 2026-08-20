"""Promotion of an optimised program, and the approval it cannot proceed without.

A newly optimised program is a challenger.  There is no code path here that promotes one
on the strength of its own evaluation score, because a program that scores itself and
then deploys itself has no independent check at any point.

The approval path is the one LASI already uses for expanding what may execute:
`update_toolbox`, bound to the package hash.  Reusing it rather than inventing a second
mechanism is deliberate — a parallel promotion path would be a weaker one that nobody
audits.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from services.contracts import ApprovalRecord

from .models import ChallengerComparison, ReasoningCapabilitySpec

#: The approval action that authorises expanding what LASI may run.
REQUIRED_ACTION = "update_toolbox"


class PromotionError(RuntimeError):
    """A challenger was asked to become champion without satisfying the conditions."""


def package_hash(program_artifact: dict[str, Any]) -> str:
    """Stable hash of a compiled program, so approval binds to exactly what was reviewed."""
    material = json.dumps(program_artifact, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def promote(
    challenger: ReasoningCapabilitySpec,
    comparison: ChallengerComparison,
    approval: ApprovalRecord | None,
) -> ReasoningCapabilitySpec:
    """Make a challenger the champion, or refuse and say why.

    Three conditions, each of which has to hold independently:

    * the comparison is admissible evidence at all,
    * the challenger actually beat the baseline,
    * a human approved *this* program, identified by hash, and that approval is
      currently in force.

    An approval for a different build does not carry over.  That is the point of binding
    to the hash: re-optimising after approval produces a different program, and a
    mechanism that let the old approval stand would authorise something nobody saw.
    """
    if challenger.standing != "challenger":
        raise PromotionError(
            f"only a challenger may be promoted; standing is {challenger.standing!r}"
        )
    if not comparison.comparable:
        raise PromotionError(
            f"comparison is not admissible evidence: {comparison.verdict} "
            f"({comparison.baseline.case_count} baseline cases, "
            f"{comparison.challenger.case_count} challenger cases, "
            f"minimum {comparison.minimum_cases})"
        )
    if not comparison.improved:
        raise PromotionError(f"challenger did not beat the baseline: {comparison.verdict}")
    if approval is None:
        raise PromotionError("promotion requires an explicit approval record")
    if approval.action_type != REQUIRED_ACTION:
        raise PromotionError(
            f"promotion requires a {REQUIRED_ACTION!r} approval, not {approval.action_type!r}"
        )
    # The existence of an approval record is not approval.  A rejected or withdrawn
    # request is still a record, and reading it as authorisation would invert its meaning.
    if approval.approval_status != "approved":
        raise PromotionError(f"approval record is {approval.approval_status!r}, not 'approved'")
    if approval.expires_at is not None and approval.expires_at <= datetime.now(UTC):
        raise PromotionError("approval has expired; re-approval is required")
    if challenger.package_hash is None:
        raise PromotionError("a challenger without a package hash cannot be approved")
    if not _binds_to(approval, challenger.package_hash):
        raise PromotionError(
            "approval is not bound to this program's package hash; "
            "an approval for a different build does not carry over"
        )
    return challenger.model_copy(update={"standing": "champion"})


def _binds_to(approval: ApprovalRecord, expected_hash: str) -> bool:
    """Whether the approval names this exact package.

    The hash may be carried in the proposal id or in the approval's own conditions;
    both are checked rather than assuming one convention.
    """
    if approval.proposal_id and expected_hash in approval.proposal_id:
        return True
    return any(expected_hash in condition for condition in approval.conditions)
