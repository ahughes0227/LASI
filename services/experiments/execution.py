"""Authorization boundary for future experiment execution services."""

import hashlib
import json

from services.contracts import DecisionRecord, ExperimentPlan


def experiment_plan_content_hash(plan: ExperimentPlan) -> str:
    """Return the canonical identity of every execution-relevant plan field."""

    payload = json.dumps(
        plan.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_allowed_decision(plan: ExperimentPlan, decision: DecisionRecord) -> None:
    """Raise unless a matching decision explicitly authorizes this plan."""

    if decision.project_id != plan.project_id:
        raise PermissionError("decision project does not match experiment plan")
    if decision.experiment_plan_id != plan.experiment_plan_id:
        raise PermissionError("decision does not authorize this experiment plan")
    if decision.experiment_plan_hash != experiment_plan_content_hash(plan):
        raise PermissionError("decision does not authorize this immutable experiment plan content")
    if not decision.allowed or decision.decision not in {"allow", "allow_with_warning"}:
        raise PermissionError("experiment plan is not allowed by the decision record")
    if (plan.approval_required or decision.approval_required) and decision.approved_by is None:
        raise PermissionError("required approval is missing")
