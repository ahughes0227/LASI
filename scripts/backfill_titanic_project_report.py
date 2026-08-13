"""Render the full project-level closeout report for the Titanic demonstration."""

# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from services.context import ArtifactContract, ICMStore
from services.contracts import ReportSection, StaticReportData
from services.contracts.models import Provenance
from services.memory import (
    ActionUsage,
    Base,
    OperationalMemory,
    create_engine,
    create_session_factory,
)
from services.reports import ReportRenderer
from services.telemetry import TokenUsageService

PROJECT_ID = "kaggle-titanic-naive"
TRAIN_PATH = Path("/private/tmp/lasi-titanic-source/train.csv")
TEST_PATH = Path("/private/tmp/lasi-titanic-source/test.csv")


def main() -> None:
    if not TRAIN_PATH.is_file() or not TEST_PATH.is_file():
        raise FileNotFoundError("Titanic source CSVs are required to produce the EDA-backed report")
    repository_root = Path(__file__).resolve().parents[1]
    store = ICMStore(repository_root)
    project_root = store.project_root(PROJECT_ID)
    engine = create_engine(f"sqlite:///{project_root / 'artifacts' / 'operational.sqlite'}")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    metering = TokenUsageService(memory)
    _record_once(metering, memory, "project-closeout-assembly", "project_report_assembly")
    _record_once(metering, memory, "project-closeout-render", "report_generation")
    report = _report(project_root, metering.project_report(PROJECT_ID))
    path = project_root / "40_output" / "reports" / report.report_id / "index.html"
    if not path.exists():
        ReportRenderer().write_immutable(report, path)
    reference = "40_output/reports/project-titanic-closeout-v1.md"
    store.write_artifact(
        PROJECT_ID,
        reference,
        f"# Project Closeout Report\n\nStatic report: {path}\n",
        overwrite=True,
        contract=ArtifactContract(capability="reporting", writes=[reference]),
    )
    print(path)


def _record_once(
    metering: TokenUsageService, memory: OperationalMemory, action_id: str, action_type: str
) -> None:
    if memory.get(ActionUsage, f"usage-{action_id}") is None:
        metering.record_not_applicable(
            project_id=PROJECT_ID,
            action_id=action_id,
            action_type=action_type,
            reason="deterministic historical report assembly does not invoke a token-metered runtime",
        )


def _complete(summary: str, **content: Any) -> ReportSection:
    return ReportSection(section_status="complete", summary=summary, content=content)


def _report(project_root: Path, telemetry: Any) -> StaticReportData:
    train = pd.read_csv(TRAIN_PATH)
    test = pd.read_csv(TEST_PATH)
    naive = _metrics(project_root, "titanic-naive-logistic-v1")
    engineered = _metrics(project_root, "titanic-title-family-logistic-v1")
    survival_by_sex = train.groupby("Sex")["Survived"].agg(["count", "mean"]).round(4)
    survival_by_class = train.groupby("Pclass")["Survived"].agg(["count", "mean"]).round(4)
    missing = train.isna().sum()
    missing = {column: int(count) for column, count in missing.items() if count}
    report_id = "project-titanic-closeout-v1"
    return StaticReportData(
        report_id=report_id,
        report_header={
            "title": "LASI project closeout: Kaggle Titanic demonstration",
            "project_id": PROJECT_ID,
            "project_name": "Kaggle Titanic full LASI demonstration",
            "problem_type": "binary classification",
            "modality": "tabular",
            "dataset_version": "kaggle-titanic:public-train-test-v1",
            "report_generated_at": datetime.now(UTC).isoformat(),
            "privacy_mode": "local_only",
            "execution_backends_used": "local + Kaggle CLI feedback",
        },
        executive_summary=_complete(
            "The title/family representation improved both local and public-baseline accuracy, "
            "but did not beat LASI's existing 0.78229 public-score benchmark. Stop this branch.",
            best_in_this_project=0.77511,
            existing_lasi_best=0.78229,
            decision="research_only; continuation requires a new approved hypothesis",
        ),
        current_decision=_complete(
            "No additional variation is authorized.",
            reason="The observed improvement does not justify unplanned tuning after external feedback.",
        ),
        dataset_summary=_complete(
            "Kaggle Titanic public train/test data: 891 labeled training rows and 418 unlabeled test rows.",
            train_rows=len(train),
            test_rows=len(test),
            train_columns=list(train.columns),
            test_columns=list(test.columns),
        ),
        dataset_characterization=_complete(
            "The dataset is binary, moderately imbalanced, and has material missingness in Age and Cabin.",
            survival_rate=round(float(train["Survived"].mean()), 4),
            missing_values=missing,
            duplicate_train_rows=int(train.duplicated().sum()),
        ),
        eda_findings=_complete(
            "Sex and passenger class are strongly associated with survival; Fare differs substantially "
            "between survivors and non-survivors, while median age is identical at 28.",
            survival_by_sex=survival_by_sex.reset_index().to_dict("records"),
            survival_by_class=survival_by_class.reset_index().to_dict("records"),
            median_fare_by_outcome={
                str(key): float(value)
                for key, value in train.groupby("Survived")["Fare"].median().items()
            },
            median_age_by_outcome={
                str(key): float(value)
                for key, value in train.groupby("Survived")["Age"].median().items()
            },
            missing_values=missing,
            source_files=[str(TRAIN_PATH), str(TEST_PATH)],
        ),
        surprising_findings=_complete(
            "The much higher local holdout score did not translate to a score above the prior public best. "
            "Also, Age's median does not separate the two outcome groups despite its common use in Titanic models.",
            local_to_public_gap={
                "naive": round(float(naive["local_accuracy"]) - 0.76794, 5),
                "title_family": round(float(engineered["local_accuracy"]) - 0.77511, 5),
            },
            age_median_same_for_both_outcomes=True,
            caveat="Associations are descriptive EDA, not causal explanations.",
        ),
        proposed_approaches=_complete(
            "LASI used a transparent baseline first, then a bounded feature representation backed by prior LASI benchmark evidence.",
            approaches=[
                {
                    "approach": "Regularized logistic-regression baseline",
                    "why": "Establish a reproducible evidence floor before optimization.",
                    "evidence_basis": "Baseline-first experimental design; no literature retrieval was performed.",
                },
                {
                    "approach": "Reviewed title/family feature representation",
                    "why": "Capture passenger-title and household structure without arbitrary feature generation.",
                    "evidence_basis": "Prior LASI Kaggle submission 55210331 scored 0.78229 publicly.",
                },
            ],
            limitation="Prior benchmark evidence supports a bounded test, not blind parameter search.",
        ),
        experiment_summary=_complete(
            "Two approved experiments were run and submitted for external feedback."
        ),
        experiments_tried=_complete(
            "The second experiment changed only the reviewed representation relative to the baseline.",
            experiments=[
                {
                    "experiment": "titanic-naive-logistic-v1",
                    "why": "Establish the baseline.",
                    "configuration": "CSV -> stratified 80/20 holdout -> logistic regression -> evaluation",
                },
                {
                    "experiment": "titanic-title-family-logistic-v1",
                    "why": "Test the benchmark-supported title/family representation.",
                    "configuration": "CSV -> title/family features -> stratified 80/20 holdout -> logistic regression -> evaluation",
                },
            ],
        ),
        results_and_interpretation=_complete(
            "The title/family run added 0.01117 local accuracy and 0.00717 public accuracy over the naive baseline, "
            "but remained 0.00718 below the existing best public result.",
            experiments=[
                {**naive, "kaggle_submission": "55470945", "public_accuracy": 0.76794},
                {**engineered, "kaggle_submission": "55470993", "public_accuracy": 0.77511},
            ],
            existing_lasi_best={"kaggle_submission": "55210331", "public_accuracy": 0.78229},
        ),
        model_comparison=_complete(
            "The engineered representation is better than the project baseline but not LASI's best."
        ),
        performance_gap_diagnosis=ReportSection(
            section_status="not_available",
            summary="No formal error-stratification study was run after the two submissions.",
            missing_or_blocked_reason="Further work requires a new approved hypothesis.",
        ),
        learning_curves=ReportSection(
            section_status="not_run", summary="Learning curves were not part of this branch."
        ),
        error_analysis=ReportSection(
            section_status="not_run", summary="Error analysis was not part of this branch."
        ),
        cluster_or_latent_analysis=ReportSection(
            section_status="not_run", summary="Latent analysis was not part of this branch."
        ),
        scientist_review=ReportSection(
            section_status="not_available",
            summary="No LASI scientist provider was invoked in this historical demonstration.",
        ),
        decision_record=_complete(
            "Both runs were governed local experiment plans; continuation is stopped."
        ),
        knowledge_context=ReportSection(
            section_status="not_available",
            summary="The project lesson is a draft promotion proposal, not approved institutional knowledge.",
        ),
        recommendation=_complete(
            "Preserve the title/family feature component as a candidate reusable capability; do not submit another variant "
            "until a new hypothesis explains how it can exceed 0.78229.",
        ),
        project_outcome=_complete(
            "research_only: the full local-to-Kaggle feedback loop was completed without deployment."
        ),
        token_telemetry=ReportSection(
            section_status="partial_success" if telemetry.unavailable_action_count else "complete",
            summary=(
                f"Measured: {telemetry.total_tokens} total tokens ({telemetry.input_tokens} input, "
                f"{telemetry.output_tokens} output, {telemetry.cached_input_tokens} cached input)."
            ),
            missing_or_blocked_reason=(
                "Three historical agent actions lack authoritative provider/runtime receipts."
                if telemetry.unavailable_action_count
                else None
            ),
            content=telemetry.model_dump(mode="json"),
        ),
        appendix=_complete(
            "Public leaderboard feedback is external evidence; LASI did not access hidden test labels.",
            evidence=[
                "30_evidence/comparisons/kaggle-feedback.md",
                "30_evidence/telemetry/action-usage.json",
            ],
        ),
        project_outcome_status="research_only",
        provenance=Provenance(
            author="titanic-project-closeout-backfill",
            source_artifacts=[
                str(TRAIN_PATH),
                str(TEST_PATH),
                "30_evidence/comparisons/kaggle-feedback.md",
                "30_evidence/telemetry/action-usage.json",
            ],
        ),
    )


def _metrics(project_root: Path, experiment_id: str) -> dict[str, Any]:
    document = json.loads(
        (project_root / "30_evidence" / "metrics" / f"{experiment_id}.json").read_text(
            encoding="utf-8"
        )
    )
    evaluation = document["evaluation"]
    if not isinstance(evaluation, dict):
        raise ValueError(f"invalid evaluation evidence: {experiment_id}")
    metrics = evaluation["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError(f"invalid metric values: {experiment_id}")
    return {
        "experiment": experiment_id,
        "local_accuracy": evaluation["primary_value"],
        "local_metrics": metrics,
    }


if __name__ == "__main__":
    main()
