"""Pure deterministic decision gates.

The service deliberately does not expose an execute method.  Recommendations
are data, and an allowed decision is necessary but not itself execution.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lasi.contracts import (
    ApprovalRecord,
    DecisionRecord,
    ExperimentPlan,
    RemoteHostProfile,
    ToolSpec,
)
from lasi.contracts.models import BudgetEstimate, PrivacyMode

from .governance import ACTION_REQUIREMENTS, ActionRequirement, ApprovalStatus, DecisionOutcome

_PRIVACY_RANK = {
    "local_only": 0,
    "summary_only_to_scientist": 1,
    "plots_allowed": 2,
    "thumbnails_allowed": 3,
    "raw_samples_allowed": 4,
    "knowledge_allowed": 5,
}
_READY_DATASET_STATUSES = frozenset({"approved", "active", "ready", "validated"})


@dataclass(frozen=True)
class Recommendation:
    """A provider recommendation, with no execution capability by design."""

    recommendation_id: str
    project_id: str
    action: str
    summary: str = ""
    requested_tool_id: str | None = None


@dataclass(frozen=True)
class DecisionContext:
    """Read-only facts supplied by owning services for gate evaluation."""

    privacy_mode: PrivacyMode | str = PrivacyMode.LOCAL_ONLY
    available_budget: BudgetEstimate = field(default_factory=BudgetEstimate)
    available_tools: tuple[ToolSpec, ...] = ()
    dataset_status: str = "unknown"
    dataset_comparable: bool = True
    remote_host: RemoteHostProfile | None = None
    remote_trust_allowed: bool = True
    duplicate_found: bool = False
    duplicate_override_reason: str | None = None
    existing_approval: ApprovalRecord | None = None
    provider_privacy_capabilities: tuple[PrivacyMode | str, ...] = ()
    policy_conflict: bool = False
    now: datetime | None = None


class DecisionGate:
    """Evaluate recommendations and plans without executing either."""

    def evaluate(
        self,
        recommendation: Recommendation,
        *,
        context: DecisionContext,
        plan: ExperimentPlan | None = None,
    ) -> DecisionRecord:
        """Return a canonical decision before any tool runner may be called.

        Experiment actions require a compiled plan.  This is the explicit
        recommendation-to-plan boundary and prevents provider output from
        becoming an executable command.
        """
        action = _normalise_action(recommendation.action)
        requirement = ACTION_REQUIREMENTS.get(action)
        common = self._common(recommendation, action, requirement, context, plan)
        if requirement is None:
            return self._record(
                **common,
                decision="request_clarification",
                allowed=False,
                missing_inputs=["supported_action_type"],
                rationale=f"Action {action!r} is not registered and cannot be authorized.",
            )
        if action == "stop_project":
            return self._record(
                **common,
                decision=DecisionOutcome.STOP_PROJECT,
                allowed=False,
                rationale="The recommendation explicitly stops the current project path.",
            )
        if action == "defer":
            return self._record(
                **common,
                decision=DecisionOutcome.DEFER,
                allowed=False,
                rationale="The recommendation is deferred until its dependency is available.",
            )
        if action in {"run_local_experiment", "run_remote_experiment"} and plan is None:
            return self._record(
                **common,
                decision="request_clarification",
                allowed=False,
                missing_inputs=["experiment_plan"],
                rationale=(
                    "A recommendation is not an executable plan; compile and evaluate "
                    "an ExperimentPlan first."
                ),
            )
        if context.policy_conflict:
            return self._record(
                **common,
                decision="escalate_for_approval",
                allowed=False,
                approval_required=True,
                blocked_by=["policy_conflict"],
                rationale="Applicable policies conflict, so automation cannot safely decide.",
            )

        checks = self._checks(action, requirement, context, plan, recommendation.project_id)
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            return self._record(
                **common,
                decision="block",
                allowed=False,
                blocked_by=failed,
                approval_required=(
                    requirement.approval_required or bool(plan and plan.approval_required)
                ),
                rationale="Blocked by: " + ", ".join(failed) + ".",
            )
        if context.duplicate_found and context.duplicate_override_reason is None:
            return self._record(
                **common,
                decision="block",
                allowed=False,
                blocked_by=["duplicate_work"],
                rationale=(
                    "An equivalent comparable run already exists; provide an explicit "
                    "replication reason or approval."
                ),
            )
        approval_required = requirement.approval_required or bool(plan and plan.approval_required)
        if approval_required and not _approval_is_valid(
            context.existing_approval, recommendation.project_id, action, context.now
        ):
            outcome = (
                "convert_to_proposal" if requirement.proposal_type else "escalate_for_approval"
            )
            return self._record(
                **common,
                decision=outcome,
                allowed=False,
                approval_required=True,
                blocked_by=["approval_required"],
                rationale=(
                    f"{action} is a protected {requirement.risk_level}-risk action and "
                    "cannot execute without human approval."
                ),
                next_action="submit_proposal"
                if requirement.proposal_type
                else "request_human_approval",
            )
        warning = _near_budget_warning(
            context.available_budget, plan.budget_estimate if plan else None
        )
        return self._record(
            **common,
            decision="allow_with_warning" if warning else "allow",
            allowed=True,
            approval_required=approval_required,
            conditions=[warning] if warning else [],
            rationale="All deterministic decision gates passed."
            + (f" {warning}" if warning else ""),
        )

    def _common(
        self,
        recommendation: Recommendation,
        action: str,
        requirement: ActionRequirement | None,
        context: DecisionContext,
        plan: ExperimentPlan | None,
    ) -> dict[str, Any]:
        return {
            "project_id": recommendation.project_id,
            "recommendation_id": recommendation.recommendation_id,
            "experiment_plan_id": plan.experiment_plan_id if plan else None,
            "action_requested": action,
            "risk_level": requirement.risk_level if requirement else "unknown",
            "context": context,
            "plan": plan,
        }

    def _checks(
        self,
        action: str,
        requirement: ActionRequirement,
        context: DecisionContext,
        plan: ExperimentPlan | None,
        project_id: str,
    ) -> dict[str, bool]:
        checks: dict[str, bool] = {
            "privacy": _privacy_allows(requirement.required_privacy, context),
            "budget": _budget_allows(
                context.available_budget, plan.budget_estimate if plan else None
            ),
            "dataset_status": context.dataset_status in _READY_DATASET_STATUSES,
            "comparability": context.dataset_comparable,
        }
        if plan is not None:
            checks["project_scope"] = plan.project_id == project_id
        if action in {"run_local_experiment", "run_remote_experiment"}:
            tool_id = plan.planned_tool_runs[0].tool_id if plan and plan.planned_tool_runs else None
            checks["tool_availability"] = _tool_available(tool_id, plan, context.available_tools)
        if action == "run_remote_experiment":
            checks["remote_trust"] = (
                context.remote_trust_allowed
                and context.remote_host is not None
                and context.remote_host.enabled
            )
        return checks

    def _record(
        self,
        *,
        project_id: str,
        recommendation_id: str,
        experiment_plan_id: str | None,
        action_requested: str,
        risk_level: str,
        context: DecisionContext,
        plan: ExperimentPlan | None,
        decision: str,
        allowed: bool,
        rationale: str,
        blocked_by: list[str] | None = None,
        missing_inputs: list[str] | None = None,
        approval_required: bool = False,
        conditions: list[str] | None = None,
        next_action: str | None = None,
    ) -> DecisionRecord:
        checks = (
            self._checks(
                action_requested,
                ACTION_REQUIREMENTS[action_requested],
                context,
                plan,
                project_id,
            )
            if action_requested in ACTION_REQUIREMENTS
            else {}
        )
        now = context.now or datetime.now(UTC)
        return DecisionRecord(
            decision_id=f"decision-{uuid4().hex}",
            project_id=project_id,
            recommendation_id=recommendation_id,
            experiment_plan_id=experiment_plan_id,
            risk_level=risk_level,
            action_requested=action_requested,
            decision=decision,
            allowed=allowed,
            approval_required=approval_required,
            blocked_by=blocked_by or [],
            missing_inputs=missing_inputs or [],
            policy_checks={key: value for key, value in checks.items()},
            privacy_checks={"privacy": checks.get("privacy", False)},
            budget_checks={"budget": checks.get("budget", False)},
            remote_execution_checks={"remote_trust": checks.get("remote_trust", True)},
            rationale=rationale,
            conditions=conditions or [],
            next_action=next_action,
            approved_by=(
                context.existing_approval.approved_by if context.existing_approval else None
            ),
            created_at=now,
        )


def _normalise_action(action: str) -> str:
    return action.strip().lower().replace(" ", "_").replace("-", "_")


def _privacy_allows(required: str | None, context: DecisionContext) -> bool:
    if required is None:
        return True
    active = _PRIVACY_RANK.get(str(context.privacy_mode), -1)
    provider = any(
        _PRIVACY_RANK.get(str(mode), -1) >= _PRIVACY_RANK[required]
        for mode in context.provider_privacy_capabilities
    )
    return active >= _PRIVACY_RANK[required] and (
        not context.provider_privacy_capabilities or provider
    )


def _budget_allows(available: BudgetEstimate, requested: BudgetEstimate | None) -> bool:
    if requested is None:
        return True
    for name in (
        "cost_usd",
        "cpu_hours",
        "gpu_hours",
        "wall_time_minutes",
        "memory_gb",
        "storage_gb",
        "human_review_hours",
    ):
        need, limit = getattr(requested, name), getattr(available, name)
        if need is not None and limit is not None and need > limit:
            return False
    return True


def _near_budget_warning(available: BudgetEstimate, requested: BudgetEstimate | None) -> str | None:
    if requested is None:
        return None
    for name in (
        "cost_usd",
        "cpu_hours",
        "gpu_hours",
        "wall_time_minutes",
        "memory_gb",
        "storage_gb",
        "human_review_hours",
    ):
        need, limit = getattr(requested, name), getattr(available, name)
        if need is not None and limit and need / limit >= 0.8:
            return f"Requested {name} is near the available budget."
    return None


def _tool_available(
    tool_id: str | None, plan: ExperimentPlan | None, tools: tuple[ToolSpec, ...]
) -> bool:
    if tool_id is None or plan is None:
        return False
    return any(
        tool.tool_id == tool_id
        and not tool.deprecated
        and tool.approval_status == "approved"
        and plan.execution_backend in tool.supported_execution_backends
        for tool in tools
    )


def _approval_is_valid(
    approval: ApprovalRecord | None,
    project_id: str,
    action: str,
    now: datetime | None,
) -> bool:
    if (
        approval is None
        or approval.project_id != project_id
        or approval.action_type != action
        or approval.approval_status != ApprovalStatus.APPROVED
    ):
        return False
    current = now or datetime.now(UTC)
    return approval.expires_at is None or approval.expires_at >= current
