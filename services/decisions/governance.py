"""Non-persistent governance rules used by the decision gate."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ActionRequirement:
    """The deterministic governance classification of an action."""

    risk_level: str
    approval_required: bool = False
    proposal_type: str | None = None
    required_privacy: str | None = None


# Names are intentionally action-oriented.  Unknown actions are not silently
# treated as safe: the gate requests clarification instead.
ACTION_REQUIREMENTS: Final[dict[str, ActionRequirement]] = {
    "stop_project": ActionRequirement("low"),
    "defer": ActionRequirement("low"),
    "run_local_experiment": ActionRequirement("low"),
    "run_remote_experiment": ActionRequirement(
        "medium", required_privacy="summary_only_to_scientist"
    ),
    "send_summary": ActionRequirement("low", required_privacy="summary_only_to_scientist"),
    "send_plots": ActionRequirement("high", True, required_privacy="plots_allowed"),
    "send_thumbnails": ActionRequirement("high", True, required_privacy="thumbnails_allowed"),
    "send_raw_samples": ActionRequirement("critical", True, required_privacy="raw_samples_allowed"),
    "modify_labels": ActionRequirement("high", True, "dataset_improvement"),
    "create_dataset_version": ActionRequirement("high", True, "dataset_improvement"),
    "delete_dataset_samples": ActionRequirement("critical", True, "dataset_change"),
    "merge_classes": ActionRequirement("high", True, "dataset_improvement"),
    "split_classes": ActionRequirement("high", True, "dataset_improvement"),
    "change_label_policy": ActionRequirement("high", True, "policy_update"),
    "change_benchmark": ActionRequirement("high", True, "benchmark_change"),
    "create_knowledge_proposal": ActionRequirement("high", False, "knowledge"),
    "approve_knowledge": ActionRequirement("critical", True, "knowledge"),
    "promote_hypothesis_to_fact": ActionRequirement("critical", True, "knowledge"),
    "update_toolbox": ActionRequirement("high", True, "toolbox_change"),
    "change_remote_host_profile": ActionRequirement("high", True, "remote_host_change"),
    "deploy_model": ActionRequirement("critical", True, "deployment"),
    "launch_foundation_training": ActionRequirement("critical", True, "foundation_training"),
}


class ApprovalStatus:
    """Canonical approval statuses accepted by the gate."""

    APPROVED: Final[str] = "approved"
    REJECTED: Final[str] = "rejected"
    PENDING: Final[str] = "pending"


class DecisionOutcome:
    """Canonical decision outcomes from the decision-system contract."""

    ALLOW: Final[str] = "allow"
    ALLOW_WITH_WARNING: Final[str] = "allow_with_warning"
    BLOCK: Final[str] = "block"
    ESCALATE_FOR_APPROVAL: Final[str] = "escalate_for_approval"
    CONVERT_TO_PROPOSAL: Final[str] = "convert_to_proposal"
    REQUEST_CLARIFICATION: Final[str] = "request_clarification"
    STOP_PROJECT: Final[str] = "stop_project"
    DEFER: Final[str] = "defer"
