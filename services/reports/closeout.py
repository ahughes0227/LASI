"""Build the required fixed-format closeout report for an experiment."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from services.contracts import (
    DecisionRecord,
    ExperimentPlan,
    ExperimentSpec,
    ProjectConfig,
    ReportSection,
    StaticReportData,
    TokenUsageReport,
    ToolRunResult,
)


class ExperimentCloseoutError(ValueError):
    """Raised when an experiment lacks mandatory closeout evidence."""


def _complete_section(summary: str, **content: Any) -> ReportSection:
    return ReportSection(section_status="complete", summary=summary, content=content)


def build_experiment_closeout_report(
    *,
    report_id: str,
    project: ProjectConfig,
    spec: ExperimentSpec,
    plan: ExperimentPlan,
    decision: DecisionRecord,
    tool_runs: tuple[ToolRunResult, ...],
    output_refs: dict[str, Path],
    eda_findings: ReportSection,
    surprising_findings: ReportSection,
    proposed_approaches: ReportSection,
    token_usage: TokenUsageReport,
) -> StaticReportData:
    """Create a report only when EDA, rationale, results, and telemetry exist."""
    required = {
        "eda_findings": eda_findings,
        "surprising_findings": surprising_findings,
        "proposed_approaches": proposed_approaches,
    }
    missing = [name for name, section in required.items() if not section.summary]
    if missing:
        raise ExperimentCloseoutError(
            "experiment closeout requires summaries for: " + ", ".join(sorted(missing))
        )
    run_status = "succeeded" if all(run.status == "succeeded" for run in tool_runs) else "failed"
    metrics = {run.tool_id: run.metrics for run in tool_runs if run.metrics}
    empty = ReportSection(
        section_status="not_run",
        summary="Not run in this experiment.",
        missing_or_blocked_reason="This analysis was outside the approved experiment plan.",
    )
    telemetry_status: Literal["complete", "partial_success"] = (
        "complete" if token_usage.unavailable_action_count == 0 else "partial_success"
    )
    return StaticReportData(
        report_id=report_id,
        report_header={
            "title": f"LASI experiment closeout: {spec.experiment_spec_id}",
            "project_id": project.project_id,
            "project_name": project.project_name,
            "problem_type": project.problem_type,
            "modality": project.modality,
            "dataset_version": spec.dataset_version_id,
            "report_generated_at": datetime.now(UTC).isoformat(),
            "privacy_mode": project.privacy_mode,
            "execution_backends_used": spec.execution_backend,
        },
        executive_summary=_complete_section(
            f"{run_status.title()} experiment: {spec.hypothesis}",
            outcome=run_status,
            primary_metrics=metrics,
        ),
        current_decision=_complete_section(
            decision.rationale,
            decision_id=decision.decision_id,
            decision=decision.decision,
            allowed=decision.allowed,
        ),
        dataset_summary=_complete_section(
            f"Dataset version {spec.dataset_version_id} was used.",
            dataset_version_id=spec.dataset_version_id,
        ),
        dataset_characterization=eda_findings,
        eda_findings=eda_findings,
        surprising_findings=surprising_findings,
        proposed_approaches=proposed_approaches,
        experiment_summary=_complete_section(
            plan.reason_for_experiment,
            hypothesis=plan.hypothesis,
            experiment_type=plan.experiment_type,
            expected_signal=plan.expected_signal,
        ),
        experiments_tried=_complete_section(
            f"Executed {len(tool_runs)} approved component actions.",
            plan_id=plan.experiment_plan_id,
            components=[
                {
                    "tool_id": run.tool_id,
                    "version": run.tool_version,
                    "status": run.status,
                    "parameters": run.parameters,
                }
                for run in tool_runs
            ],
        ),
        results_and_interpretation=_complete_section(
            f"Component graph finished with status {run_status}.",
            metrics=metrics,
            output_artifacts={name: str(path) for name, path in sorted(output_refs.items())},
        ),
        model_comparison=empty,
        performance_gap_diagnosis=empty,
        learning_curves=empty,
        error_analysis=empty,
        cluster_or_latent_analysis=empty,
        scientist_review=ReportSection(
            section_status="not_available",
            summary="No scientist-provider review was invoked by this component workflow.",
            missing_or_blocked_reason=(
                "A deterministic component run does not infer a provider review."
            ),
        ),
        scientific_criticism=ReportSection(
            section_status="not_run",
            summary="No independent scientific critic result was available for this closeout.",
            missing_or_blocked_reason="Criticism is scheduled by the semantic task runtime.",
        ),
        decision_record=_complete_section(
            "Decision record validated before execution.", decision_id=decision.decision_id
        ),
        knowledge_context=ReportSection(
            section_status="not_available",
            summary="No approved institutional knowledge was retrieved for this closeout.",
            missing_or_blocked_reason=(
                "Project evidence and cited approach rationale remain distinct "
                "from approved knowledge."
            ),
        ),
        recommendation=_complete_section(
            (
                "Interpret results against the stated success and failure criteria "
                "before authorizing follow-up."
            ),
            success_criteria=plan.success_criteria,
            failure_criteria=plan.failure_criteria,
        ),
        project_outcome=ReportSection(
            section_status="not_available",
            summary="Experiment closeout does not itself assign a project outcome.",
            missing_or_blocked_reason="Outcome transitions remain owned by the outcome system.",
        ),
        token_telemetry=ReportSection(
            section_status=telemetry_status,
            summary=(
                f"Measured total: {token_usage.total_tokens} tokens "
                f"({token_usage.input_tokens} input, {token_usage.output_tokens} output, "
                f"{token_usage.cached_input_tokens} cached input)."
            ),
            missing_or_blocked_reason=(
                "Some agent/provider actions have no authoritative receipt."
                if token_usage.unavailable_action_count
                else None
            ),
            content=token_usage.model_dump(mode="json"),
        ),
        appendix=_complete_section("Resolved specification and output artifacts are listed above."),
        project_outcome_status="pending",
    )
