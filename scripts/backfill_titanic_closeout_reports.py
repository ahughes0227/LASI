"""Create immutable closeout reports for Titanic runs completed before report gating."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.context import ICMStore
from services.contracts import ReportSection, StaticReportData, TokenUsageReport
from services.contracts.models import Provenance
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.reports import ReportRenderer
from services.telemetry import TokenUsageService

PROJECT_ID = "kaggle-titanic-naive"
EXPERIMENTS = {
    "naive": ("titanic-naive-logistic-v1", "55470945", 0.76794),
    "title-family": ("titanic-title-family-logistic-v1", "55470993", 0.77511),
}


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    store = ICMStore(repository_root)
    project_root = store.project_root(PROJECT_ID)
    engine = create_engine(f"sqlite:///{project_root / 'artifacts' / 'operational.sqlite'}")
    Base.metadata.create_all(engine)
    telemetry = TokenUsageService(OperationalMemory(create_session_factory(engine))).project_report(
        PROJECT_ID
    )
    for variant, (experiment_id, submission_id, public_score) in EXPERIMENTS.items():
        metric_path = project_root / "30_evidence" / "metrics" / f"{experiment_id}.json"
        metrics = json.loads(metric_path.read_text(encoding="utf-8"))
        report = _report(variant, experiment_id, submission_id, public_score, metrics, telemetry)
        path = project_root / "40_output" / "reports" / report.report_id / "index.html"
        if not path.exists():
            ReportRenderer().write_immutable(report, path)
        print(path)


def _report(
    variant: str,
    experiment_id: str,
    submission_id: str,
    public_score: float,
    metrics: dict[str, Any],
    telemetry: TokenUsageReport,
) -> StaticReportData:
    evaluation = metrics["evaluation"]
    if not isinstance(evaluation, dict):
        raise ValueError(f"invalid evaluation evidence for {experiment_id}")
    local_score = evaluation["primary_value"]
    if not isinstance(local_score, (int, float)):
        raise ValueError(f"invalid primary metric for {experiment_id}")

    def section(summary: str, **content: Any) -> ReportSection:
        return ReportSection(section_status="complete", summary=summary, content=content)

    historical_gap = ReportSection(
        section_status="not_available",
        summary="Historical runs predate the mandatory EDA contract.",
        missing_or_blocked_reason=(
            "The completed project retained metrics and submissions but not a full source-data "
            "EDA artifact. This gap is not reconstructed from memory."
        ),
    )
    approach = (
        "A transparent logistic-regression baseline establishes an evidence floor."
        if variant == "naive"
        else "A bounded title/family feature representation tests prior LASI benchmark evidence."
    )
    research = (
        "Methodological baseline; no external literature retrieval occurred."
        if variant == "naive"
        else "Prior LASI public benchmark submission 55210331 scored 0.78229."
    )
    report_id = f"report-{experiment_id}-backfill-v1"
    return StaticReportData(
        report_id=report_id,
        report_header={
            "title": f"LASI experiment closeout: {experiment_id}",
            "project_id": PROJECT_ID,
            "problem_type": "binary_classification",
            "modality": "tabular",
            "dataset_version": "kaggle-titanic:public-train-test-v1",
            "report_generated_at": datetime.now(UTC).isoformat(),
        },
        executive_summary=section(
            (
                f"Local accuracy was {float(local_score):.5f}; Kaggle public accuracy "
                f"was {public_score:.5f}."
            ),
            status="completed historical experiment",
        ),
        current_decision=section(
            "No further variation was authorized in this branch.",
            decision="research_only",
        ),
        dataset_summary=section("Titanic public train/test benchmark data was used."),
        dataset_characterization=historical_gap,
        eda_findings=historical_gap,
        surprising_findings=historical_gap,
        proposed_approaches=section(approach, research_basis=research),
        experiment_summary=section("Approved component graph completed.", variant=variant),
        experiments_tried=section(
            "One configuration was run for this experiment report.",
            experiment_id=experiment_id,
            rationale=approach,
        ),
        results_and_interpretation=section(
            "External leaderboard feedback is retained separately from local holdout evidence.",
            local_evaluation=evaluation,
            kaggle_submission_id=submission_id,
            kaggle_public_accuracy=public_score,
        ),
        model_comparison=ReportSection(
            section_status="not_available",
            summary="Cross-experiment comparison is in kaggle-feedback.md.",
        ),
        performance_gap_diagnosis=ReportSection(section_status="not_run"),
        learning_curves=ReportSection(section_status="not_run"),
        error_analysis=ReportSection(section_status="not_run"),
        cluster_or_latent_analysis=ReportSection(section_status="not_run"),
        scientist_review=ReportSection(
            section_status="not_available",
            summary="No LASI scientist provider was invoked for this historical run.",
        ),
        decision_record=section("Decision evidence is retained in the metrics artifact."),
        knowledge_context=ReportSection(
            section_status="not_available",
            summary=(
                "The project lesson remains a draft promotion proposal, not approved knowledge."
            ),
        ),
        recommendation=section(
            "Do not tune further without a new approved hypothesis that could beat 0.78229."
        ),
        project_outcome=section("Project branch outcome is research_only."),
        token_telemetry=ReportSection(
            section_status=(
                "partial_success" if telemetry.unavailable_action_count else "complete"
            ),
            summary=(
                f"Project-wide measured total: {telemetry.total_tokens} tokens "
                f"({telemetry.input_tokens} input, {telemetry.output_tokens} output)."
            ),
            missing_or_blocked_reason=(
                "Historical agent actions have no authoritative token receipt."
                if telemetry.unavailable_action_count
                else None
            ),
            content=telemetry.model_dump(mode="json"),
        ),
        appendix=section(
            "Backfilled from durable project metrics, Kaggle feedback, and telemetry."
        ),
        project_outcome_status="research_only",
        provenance=Provenance(
            author="telemetry-and-report-backfill",
            source_artifacts=[
                f"30_evidence/metrics/{experiment_id}.json",
                "30_evidence/comparisons/kaggle-feedback.md",
                "30_evidence/telemetry/action-usage.json",
            ],
        ),
    )


if __name__ == "__main__":
    main()
