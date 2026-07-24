"""Authorization boundary for future experiment execution services."""

from lasi.contracts import DecisionRecord, ExperimentPlan


def require_allowed_decision(plan: ExperimentPlan, decision: DecisionRecord) -> None:
    """Raise unless a matching decision explicitly authorizes this plan."""

    if decision.project_id != plan.project_id:
        raise PermissionError("decision project does not match experiment plan")
    if decision.experiment_plan_id != plan.experiment_plan_id:
        raise PermissionError("decision does not authorize this experiment plan")
    if not decision.allowed or decision.decision not in {"allow", "allow_with_warning"}:
        raise PermissionError("experiment plan is not allowed by the decision record")
    if (plan.approval_required or decision.approval_required) and decision.approved_by is None:
        raise PermissionError("required approval is missing")
