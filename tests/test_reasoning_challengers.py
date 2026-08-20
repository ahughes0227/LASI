"""An optimised program is a challenger until someone approves it.

The property under test is not that optimisation works. It is that no amount of
self-reported improvement lets a program deploy itself, and that an approval authorises
exactly the build it was given.
"""

from datetime import UTC, datetime, timedelta

import pytest
from services.contracts import ApprovalRecord
from services.reasoning import (
    CaseScore,
    ChallengerComparison,
    CriterionScore,
    EvaluationResult,
    PromotionError,
    ReasoningCapabilitySpec,
    package_hash,
    promote,
)

NOW = datetime.now(UTC)
HASH = package_hash({"program_id": "diagnose", "state": {"demos": []}})


def _result(passed: int, total: int, *, version: str) -> EvaluationResult:
    return EvaluationResult(
        program_id="diagnose",
        program_version=version,
        rubric_id="scientific_review",
        rubric_version="1.0",
        scores=[
            CaseScore(
                case_id=f"case-{index}",
                criteria=[
                    CriterionScore(criterion_id="grounded", satisfied=index < passed, required=True)
                ],
            )
            for index in range(total)
        ],
    )


def _comparison(baseline_passed: int, challenger_passed: int, total: int = 10):
    return ChallengerComparison(
        baseline=_result(baseline_passed, total, version="1.0"),
        challenger=_result(challenger_passed, total, version="2.0"),
    )


def _challenger(**overrides) -> ReasoningCapabilitySpec:
    base = {
        "program_id": "diagnose",
        "program_version": "2.0",
        "capability_id": "critique",
        "rubric_id": "scientific_review",
        "rubric_version": "1.0",
        "standing": "challenger",
        "package_hash": HASH,
    }
    return ReasoningCapabilitySpec(**{**base, **overrides})


def _approval(**overrides) -> ApprovalRecord:
    base = {
        "approval_id": "approval-1",
        "project_id": "project-1",
        "proposal_id": f"proposal-{HASH}",
        "action_type": "update_toolbox",
        "risk_level": "medium",
        "requested_by": "lasi",
        "approved_by": "andrew",
        "approval_status": "approved",
        "created_at": NOW,
    }
    return ApprovalRecord(**{**base, **overrides})


def test_an_approved_and_better_challenger_becomes_champion() -> None:
    promoted = promote(_challenger(), _comparison(5, 8), _approval())

    assert promoted.standing == "champion"
    # The original spec is unchanged; promotion returns a new one.
    assert _challenger().standing == "challenger"


def test_a_better_challenger_still_cannot_self_promote() -> None:
    """The single most important behaviour in this module."""
    with pytest.raises(PromotionError, match="explicit approval"):
        promote(_challenger(), _comparison(5, 10), None)


def test_a_worse_challenger_is_refused() -> None:
    with pytest.raises(PromotionError, match="did not beat"):
        promote(_challenger(), _comparison(8, 5), _approval())


def test_a_tie_is_not_an_improvement() -> None:
    with pytest.raises(PromotionError, match="did not beat"):
        promote(_challenger(), _comparison(6, 6), _approval())


def test_too_few_cases_is_not_evidence() -> None:
    """A pass-rate difference over three cases is noise dressed as a result."""
    with pytest.raises(PromotionError, match="not admissible evidence"):
        promote(_challenger(), _comparison(0, 3, total=3), _approval())


def test_comparison_over_different_case_counts_is_refused() -> None:
    mismatched = ChallengerComparison(
        baseline=_result(5, 10, version="1.0"), challenger=_result(6, 8, version="2.0")
    )

    assert mismatched.comparable is False
    with pytest.raises(PromotionError, match="not admissible evidence"):
        promote(_challenger(), mismatched, _approval())


def test_an_approval_for_a_different_build_does_not_carry_over() -> None:
    """Re-optimising after approval produces a program nobody reviewed."""
    stale = _approval(proposal_id="proposal-" + "0" * 64)

    with pytest.raises(PromotionError, match="package hash"):
        promote(_challenger(), _comparison(5, 8), stale)


def test_a_rejected_approval_record_is_not_approval() -> None:
    """The existence of a record is not consent; reading it as such inverts its meaning."""
    with pytest.raises(PromotionError, match="not 'approved'"):
        promote(_challenger(), _comparison(5, 8), _approval(approval_status="rejected"))


def test_an_expired_approval_is_refused() -> None:
    expired = _approval(expires_at=NOW - timedelta(days=1))

    with pytest.raises(PromotionError, match="expired"):
        promote(_challenger(), _comparison(5, 8), expired)


def test_the_wrong_kind_of_approval_is_refused() -> None:
    with pytest.raises(PromotionError, match="update_toolbox"):
        promote(_challenger(), _comparison(5, 8), _approval(action_type="run_experiment"))


def test_a_champion_cannot_be_promoted_again() -> None:
    with pytest.raises(PromotionError, match="only a challenger"):
        promote(_challenger(standing="champion"), _comparison(5, 8), _approval())


def test_a_challenger_without_a_hash_cannot_be_approved() -> None:
    with pytest.raises(PromotionError, match="package hash"):
        promote(_challenger(package_hash=None), _comparison(5, 8), _approval())


def test_package_hash_is_stable_and_content_addressed() -> None:
    assert package_hash({"a": 1, "b": 2}) == package_hash({"b": 2, "a": 1})
    assert package_hash({"a": 1}) != package_hash({"a": 2})
