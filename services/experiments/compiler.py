"""Deterministic compilation of recommendations into frozen experiment plans."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from services.contracts import ExperimentPlan, ToolSpec
from services.contracts.models import PlannedToolRun

MVP_EXPERIMENT_TYPES = (
    "baseline_probe",
    "learning_curve",
    "embedding_or_cluster_analysis",
    "error_analysis",
    "static_report_generation",
)

_DEFAULT_TOOLS: dict[str, tuple[str, ...]] = {
    "baseline_probe": ("train_baseline_model",),
    "learning_curve": ("compute_learning_curve",),
    "embedding_or_cluster_analysis": ("generate_embeddings", "run_hdbscan_clustering"),
    "error_analysis": ("build_error_buckets",),
    "static_report_generation": ("render_static_report",),
}


@dataclass(frozen=True)
class CompilationResult:
    """A draft plan plus checks the decision system must evaluate."""

    plan: ExperimentPlan
    required_approvals: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    estimated_cost: dict[str, float] | None = None


def _stable_id(prefix: str, value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


class ExperimentPlanCompiler:
    """Compile only the MVP experiment taxonomy; never authorize execution."""

    def __init__(self, tool_registry: Iterable[ToolSpec] = ()) -> None:
        self._tools = {tool.tool_id: tool for tool in tool_registry}

    def compile(
        self,
        recommendation: Mapping[str, Any],
        *,
        created_at: datetime | None = None,
        created_by: str | None = None,
    ) -> CompilationResult:
        experiment_type = str(recommendation.get("experiment_type", ""))
        if experiment_type not in MVP_EXPERIMENT_TYPES:
            raise ValueError(f"unsupported MVP experiment type: {experiment_type!r}")

        project_id = self._required(recommendation, "project_id")
        dataset_version = self._required(recommendation, "dataset_version")
        hypothesis = self._required(recommendation, "hypothesis")
        reason = str(recommendation.get("reason_for_experiment", hypothesis))
        backend = str(recommendation.get("execution_backend", "local"))
        if backend not in {"local", "remote"}:
            raise ValueError(f"unsupported execution backend: {backend!r}")

        requested_runs = recommendation.get("planned_tool_runs")
        tool_ids = (
            tuple(
                str(run["tool_id"] if "tool_id" in run else run["tool"]) for run in requested_runs
            )
            if requested_runs is not None
            else _DEFAULT_TOOLS[experiment_type]
        )
        plan_basis = {
            "project_id": project_id,
            "dataset_version": dataset_version,
            "experiment_type": experiment_type,
            "hypothesis": hypothesis,
            "tool_ids": tool_ids,
            "planned_tool_runs": requested_runs or [],
            "execution_backend": backend,
            "remote_host_profile": recommendation.get("remote_host_profile"),
            "expected_artifacts": recommendation.get("expected_artifacts", []),
            "privacy_mode": recommendation.get("privacy_mode", "local_only"),
        }
        plan_id = str(recommendation.get("experiment_plan_id", _stable_id("plan", plan_basis)))

        runs: list[PlannedToolRun] = []
        for index, tool_id in enumerate(tool_ids):
            source = requested_runs[index] if requested_runs is not None else {}
            runs.append(
                PlannedToolRun(
                    tool_id=tool_id,
                    run_id=source.get("run_id", f"{plan_id}-run-{index + 1}"),
                    inputs=list(source.get("inputs", [dataset_version])),
                    parameters=dict(source.get("parameters", {})),
                )
            )

        blocked: list[str] = []
        if backend == "remote" and not recommendation.get("remote_host_profile"):
            blocked.append("remote execution requires a remote_host_profile")
        for tool_id in tool_ids:
            tool = self._tools.get(tool_id)
            if tool is None and self._tools:
                blocked.append(f"tool is unavailable: {tool_id}")
            elif tool is not None:
                if tool.deprecated or tool.approval_status != "approved":
                    blocked.append(f"tool is not approved: {tool_id}")
                if backend not in tool.supported_execution_backends:
                    blocked.append(f"tool does not support backend {backend}: {tool_id}")

        plan = ExperimentPlan(
            experiment_plan_id=plan_id,
            project_id=project_id,
            ticket_id=recommendation.get("ticket_id"),
            dataset_version=dataset_version,
            hypothesis=hypothesis,
            reason_for_experiment=reason,
            experiment_type=experiment_type,
            planned_tool_runs=runs,
            execution_backend=backend,
            remote_host_profile=recommendation.get("remote_host_profile"),
            expected_artifacts=list(recommendation.get("expected_artifacts", [])),
            expected_signal=str(
                recommendation.get(
                    "expected_signal", "Evidence is produced for the stated hypothesis."
                )
            ),
            success_criteria=str(
                recommendation.get("success_criteria", "Required evidence is produced.")
            ),
            failure_criteria=str(
                recommendation.get("failure_criteria", "Required evidence cannot be produced.")
            ),
            budget_estimate=recommendation.get("budget_estimate", {}),
            privacy_mode=recommendation.get("privacy_mode", "local_only"),
            # A recorded decision is always required. Human approval is required
            # only when the plan explicitly crosses a governed boundary; using an
            # already-approved remote host is not itself such a boundary.
            approval_required=bool(recommendation.get("approval_required", False)),
            decision_record_required=True,
            stop_condition=recommendation.get("stop_condition"),
            handoff_after_decision=recommendation.get("handoff_after_decision"),
            created_by=created_by or recommendation.get("created_by"),
            created_at=created_at,
            provenance=recommendation.get("provenance", {}),
        )
        return CompilationResult(
            plan=plan,
            required_approvals=("decision_record",) if plan.approval_required else (),
            blocked_reasons=tuple(blocked),
            estimated_cost=(
                dict(recommendation["budget_estimate"])
                if recommendation.get("budget_estimate")
                else None
            ),
        )

    @staticmethod
    def _required(recommendation: Mapping[str, Any], field: str) -> str:
        value = recommendation.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"recommendation requires non-empty {field}")
        return value


def compile_plan(
    recommendation: Mapping[str, Any],
    *,
    tool_registry: Iterable[ToolSpec] = (),
    created_at: datetime | None = None,
    created_by: str | None = None,
) -> CompilationResult:
    """Functional facade for deterministic MVP plan compilation."""

    return ExperimentPlanCompiler(tool_registry).compile(
        recommendation, created_at=created_at, created_by=created_by
    )
