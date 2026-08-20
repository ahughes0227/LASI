"""Record planning decisions and token usage to MLflow.

MLflow answers two questions the relational store is not shaped for: why a path was
chosen, and whether one ranker performs better than another across many runs.

It is written to and never read back.  Operational state stays authoritative in the
database (ADR-004); any code path that consulted MLflow to decide what to do next would
make an observability system load-bearing, which is a defect rather than a feature.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from services.contracts import ActionTokenUsage, TokenUsageStatus

from .models import PlanningTrace

#: MLflow's filesystem store is in maintenance mode and refuses to initialise, so a
#: database backend is required.  SQLite is the local default; point this at the same
#: PostgreSQL the operational store uses to keep one datastore (ADR-003).
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"
DEFAULT_EXPERIMENT = "lasi-planning"


class MlflowTracer:
    """Write-only adapter for decision traces."""

    def __init__(
        self, tracking_uri: str | None = None, *, experiment: str = DEFAULT_EXPERIMENT
    ) -> None:
        self.tracking_uri = (
            tracking_uri or os.environ.get("LASI_MLFLOW_TRACKING_URI") or DEFAULT_TRACKING_URI
        )
        self.experiment = experiment
        self._configured = False

    def _configure(self) -> Any:
        # Imported lazily: MLflow is slow to import and most code paths never trace.
        import mlflow

        if not self._configured:
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment)
            self._configured = True
        return mlflow

    @contextmanager
    def run(self, run_name: str) -> Iterator[Any]:
        mlflow = self._configure()
        with mlflow.start_run(run_name=run_name) as active:
            yield active

    def log_planning_decision(self, trace: PlanningTrace) -> str:
        """Record one planning decision and return its run id."""
        mlflow = self._configure()
        with mlflow.start_run(run_name=f"plan-{trace.plan_id}") as active:
            mlflow.log_params(
                {
                    "plan_id": trace.plan_id,
                    "project_id": trace.project_id,
                    "goal_id": trace.goal_id,
                    "ranker_id": trace.ranker_id,
                    "ranker_version": trace.ranker_version,
                    "problem_digest": trace.problem_digest or "none",
                    "scaffold_revision": trace.scaffold_revision or "none",
                    "chosen_capability_ids": ",".join(trace.chosen_capability_ids) or "none",
                }
            )
            mlflow.log_metrics(
                {
                    "admissible_count": float(trace.admissible_count),
                    "chosen_step_count": float(len(trace.chosen_capability_ids)),
                    "rejected_capability_count": float(trace.rejected_capability_count),
                    # Recorded as a metric so runs where selection was forced can be
                    # filtered out of any ranker comparison.
                    "was_a_real_choice": float(trace.was_a_real_choice),
                }
            )
            for candidate_id, score in sorted(trace.precedent.items()):
                mlflow.log_metric(f"precedent.{candidate_id}", score)
            mlflow.set_tags({"status": trace.status, "lasi.record": "planning_decision"})
            return str(active.info.run_id)

    def log_token_usage(self, usage: ActionTokenUsage) -> None:
        """Record metering for one action.

        Must be called inside an active run.  MLflow's fluent API would otherwise create
        one implicitly, scattering metering across orphan runs that belong to no action.

        Token counts are logged only when the runtime returned an authoritative receipt.
        When it did not, the status and its reason are recorded and no number is
        invented: an estimate logged beside real receipts would be indistinguishable
        from one, and every later cost total would silently include fiction.
        """
        mlflow = self._configure()
        if mlflow.active_run() is None:
            raise RuntimeError("log_token_usage requires an active run; use tracer.run(...)")
        mlflow.set_tags(
            {
                "token_status": str(usage.status),
                "action_type": usage.action_type,
                "model_name": usage.model_name or "none",
            }
        )
        if usage.status != TokenUsageStatus.REPORTED or usage.usage is None:
            mlflow.set_tag("token_unavailable_reason", usage.unavailable_reason or "not_applicable")
            return

        receipt = usage.usage
        metrics = {"total_tokens": float(receipt.total_tokens)}
        if receipt.input_tokens is not None:
            metrics["input_tokens"] = float(receipt.input_tokens)
        if receipt.output_tokens is not None:
            metrics["output_tokens"] = float(receipt.output_tokens)
        if receipt.billed_cost_usd is not None:
            metrics["billed_cost_usd"] = float(receipt.billed_cost_usd)
        mlflow.log_metrics(metrics)
        mlflow.set_tag("token_reporting_source", receipt.reporting_source)


def trace_from_plan(
    plan: Any,
    *,
    problem_digest: str | None = None,
    scaffold_revision: str | None = None,
    precedent: dict[str, float] | None = None,
) -> PlanningTrace:
    """Build a trace from a `DomainPlan`.

    `admissible_count` is the chosen plan plus the alternatives retained on the plan,
    which is a lower bound when retention was capped.  Recorded as such rather than
    inflated: understating the choice is recoverable, overstating it is not.
    """
    return PlanningTrace(
        plan_id=plan.plan_id,
        project_id=plan.goal.project_id,
        goal_id=plan.goal.goal_id,
        status=plan.status,
        ranker_id=plan.ranker_id,
        ranker_version=plan.ranker_version,
        admissible_count=len(plan.considered_alternatives) + (1 if plan.steps else 0),
        chosen_capability_ids=[step.capability_id for step in plan.steps],
        rejected_capability_count=len(plan.rejected_capabilities),
        problem_digest=problem_digest,
        scaffold_revision=scaffold_revision,
        precedent=dict(precedent or {}),
    )
