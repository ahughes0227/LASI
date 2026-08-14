"""Run LASI's governed naive component pipeline on local Titanic CSV files.

The source CSVs must already be supplied locally. This script never downloads,
submits to Kaggle, reads hidden labels, or invokes a scientist provider.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from services.benchmarks import prediction_artifact_from_file, validate_submission
from services.components import ComponentRegistry, register_tabular_components
from services.context import ArtifactContract, ICMStore
from services.contracts import (
    ChallengeSpec,
    ComponentInvocation,
    EvaluationPolicy,
    ExperimentSpec,
    ProjectConfig,
    ReportSection,
)
from services.contracts.models import PrivacyMode, Provenance
from services.core import MlflowArtifactStore
from services.decisions import DecisionContext, DecisionGate, Recommendation
from services.isolation import benchmark_default
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.tools import ToolRegistry, register_builtin_tools
from services.workflows import ComponentExperimentRequest, run_component_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--project-id", default="kaggle-titanic-naive")
    parser.add_argument(
        "--variant",
        choices=("naive", "title-family"),
        default="naive",
        help="Use the naive baseline or the reviewed title/family feature composition.",
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    project_store = ICMStore(repository_root)
    project_root = project_store.project_root(args.project_id)
    (project_root / "artifacts").mkdir(parents=True, exist_ok=True)
    operational_db = project_root / "artifacts" / "operational.sqlite"
    operational_engine = create_engine(f"sqlite:///{operational_db}")
    Base.metadata.create_all(operational_engine)
    operational_memory = OperationalMemory(create_session_factory(operational_engine))
    registry = register_tabular_components(ComponentRegistry())
    spec = ExperimentSpec(
        experiment_spec_id=f"titanic-{args.variant}-logistic-v1",
        project_id=args.project_id,
        dataset_version_id="kaggle-titanic:public-train-test-v1",
        hypothesis=(
            "A naive logistic baseline establishes a reproducible Titanic evidence floor."
            if args.variant == "naive"
            else "A reviewed title/family feature representation improves the baseline."
        ),
        modality="tabular",
        problem_type="classification",
        random_seed=42,
        expected_outputs=["submission.csv", "evaluation.json"],
        provenance=Provenance(author="titanic-component-demo"),
        component_graph=_graph(args),
    )
    tools = register_builtin_tools(ToolRegistry())
    from services.components import ExperimentSpecResolver
    from services.experiments import compile_component_plan

    resolved = ExperimentSpecResolver(registry).resolve(spec)
    planned = compile_component_plan(
        resolved,
        reason_for_experiment=(
            "Establish a transparent baseline before any tuning."
            if args.variant == "naive"
            else "Test the prior leaderboard-supported title/family representation."
        ),
        expected_signal=(
            "Validation accuracy and a valid Kaggle-format submission are produced."
            if args.variant == "naive"
            else "The feature composition improves held-out and leaderboard accuracy over baseline."
        ),
        success_criteria="All components run and the submission has 418 rows.",
        failure_criteria="Any component, validation, or submission-format contract fails.",
        created_by="titanic-component-demo",
    )
    decision = DecisionGate().evaluate(
        Recommendation(
            recommendation_id=f"recommendation-titanic-{args.variant}-v1",
            project_id=spec.project_id,
            action="run_local_experiment",
        ),
        context=DecisionContext(dataset_status="validated", available_tools=tools.all()),
        plan=planned,
    )
    eda_findings, surprising_findings = _eda_sections(args.train, args.test)
    result = run_component_experiment(
        ComponentExperimentRequest(
            spec=spec,
            reason_for_experiment=planned.reason_for_experiment,
            expected_signal=planned.expected_signal,
            success_criteria=planned.success_criteria,
            failure_criteria=planned.failure_criteria,
            decision=decision,
            benchmark_protected=True,
            isolation_profile=benchmark_default(),
            artifact_store=MlflowArtifactStore(project_root / "artifacts" / "mlruns"),
            project_config=ProjectConfig(
                project_id=args.project_id,
                project_name="Kaggle Titanic full LASI demonstration",
                problem_type="binary_classification",
                modality="tabular",
                privacy_mode=PrivacyMode.LOCAL_ONLY,
                evaluation_policy=EvaluationPolicy(
                    policy_id="titanic_accuracy", primary_metric="accuracy"
                ),
            ),
            operational_memory=operational_memory,
            eda_findings=eda_findings,
            surprising_findings=surprising_findings,
            proposed_approaches=_approach_section(args.variant),
        ),
        registry=registry,
        run_root=project_root
        / "20_work"
        / "experiments"
        / spec.experiment_spec_id
        / "artifacts"
        / "component-run",
        icm_store=project_store,
    )
    submission = result.output_refs["model.test_predictions"]
    destination = project_root / "40_output" / f"submission-{args.variant}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(submission.read_bytes())
    challenge = ChallengeSpec(
        challenge_id="kaggle-titanic",
        project_id=spec.project_id,
        title="Titanic - Machine Learning from Disaster",
        brief="Public local benchmark demonstration.",
        problem_type="binary_classification",
        modalities=["tabular"],
        train_sources=[str(args.train.resolve())],
        test_sources=[str(args.test.resolve())],
        target_columns=["Survived"],
        identifier_columns=["PassengerId"],
        prediction_columns=["Survived"],
        evaluation_metric="accuracy",
        evaluation_direction="maximize",
        submission_format="csv",
        random_seed_policy="fixed:42",
        external_data_policy="deny_after_local_intake",
        internet_policy="deny_during_execution",
        hidden_label_policy="evaluator_only",
    )
    prediction_artifact = prediction_artifact_from_file(
        challenge,
        destination,
        model_run_id=result.plan.experiment_plan_id,
        source_test_dataset_version=spec.dataset_version_id,
        generating_tool="naive_logistic_classifier",
        generating_tool_version="1.0",
        row_count=418,
    )
    submission_validation = validate_submission(
        challenge,
        prediction_artifact,
        destination,
        expected_ids={str(identifier) for identifier in range(892, 1310)},
    )
    if submission_validation.status != "validated":
        raise RuntimeError(f"submission validation failed: {submission_validation.errors}")
    evaluation = json.loads(result.output_refs["evaluation.evaluation"].read_text(encoding="utf-8"))
    summary = {
        "variant": args.variant,
        "experiment_plan_id": result.plan.experiment_plan_id,
        "decision_id": result.decision.decision_id,
        "decision": result.decision.decision,
        "resolved_spec": str(result.resolved_spec_path),
        "submission": str(destination),
        "evaluation": evaluation,
        "submission_validation": submission_validation.model_dump(mode="json"),
        "artifact_uris": [record.artifact_uri for record in result.artifacts],
    }
    record_contract = ArtifactContract(
        capability="evaluation",
        writes=[f"30_evidence/metrics/{spec.experiment_spec_id}.json"],
    )
    project_store.write_artifact(
        spec.project_id,
        f"30_evidence/metrics/{spec.experiment_spec_id}.json",
        json.dumps(summary, indent=2),
        contract=record_contract,
    )
    print(json.dumps(summary, indent=2))


def _eda_sections(train_path: Path, test_path: Path) -> tuple[ReportSection, ReportSection]:
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    target_rate = float(train["Survived"].mean())
    missing = train.isna().sum().sort_values(ascending=False)
    missing = {column: int(count) for column, count in missing.items() if count}
    shared = sorted(set(train.columns) & set(test.columns))
    return (
        ReportSection(
            section_status="complete",
            summary=(
                f"Training data has {len(train)} rows and {len(train.columns)} columns; "
                f"test data has {len(test)} rows. Survival prevalence is {target_rate:.1%}."
            ),
            content={
                "train_rows": len(train),
                "test_rows": len(test),
                "shared_feature_columns": shared,
                "missing_values": missing or "No missing values found.",
                "duplicate_train_rows": int(train.duplicated().sum()),
            },
            source_artifacts=[str(train_path.resolve()), str(test_path.resolve())],
        ),
        ReportSection(
            section_status="complete",
            summary=(
                "Age and Cabin contain substantial missingness; title and family features are "
                "therefore evaluated as bounded representations rather than treating raw names "
                "or cabin text as unreviewed model inputs."
            ),
            content={
                "highest_missing_columns": dict(list(missing.items())[:3]),
                "interpretation": (
                    "Missingness and structured passenger-name information motivate a reviewed "
                    "feature representation, but do not prove leaderboard improvement."
                ),
            },
            source_artifacts=[str(train_path.resolve())],
        ),
    )


def _approach_section(variant: str) -> ReportSection:
    if variant == "naive":
        return ReportSection(
            section_status="complete",
            summary="A regularized logistic baseline was selected as a transparent evidence floor.",
            content={
                "approach": "one-hot categorical and scaled numeric logistic regression",
                "research_basis": (
                    "Baseline-first experimental design; no external literature retrieval was "
                    "performed for this run."
                ),
                "evidence_type": "methodological baseline",
            },
        )
    return ReportSection(
        section_status="complete",
        summary=(
            "A fixed title/family feature component was selected from prior "
            "LASI benchmark evidence."
        ),
        content={
            "approach": "reviewed Titanic title, family-size, and alone-status features",
            "research_basis": "Prior LASI public benchmark submission 55210331 (0.78229 accuracy).",
            "evidence_type": "project-local benchmark evidence, not a literature claim",
            "limitation": "The evidence supports a bounded test, not unconstrained feature tuning.",
        },
        source_records=["Kaggle submission 55210331"],
    )


def _graph(args: argparse.Namespace) -> list[ComponentInvocation]:
    graph: list[dict[str, object]] = [
        {
            "node_id": "dataset",
            "component_id": "tabular_csv_dataset",
            "component_version": "1.0",
            "config": {
                "train_path": str(args.train.resolve()),
                "test_path": str(args.test.resolve()),
                "target_column": "Survived",
                "identifier_columns": ["PassengerId"],
            },
        },
    ]
    dataset_ref = "dataset.dataset"
    if args.variant == "title-family":
        graph.append(
            {
                "node_id": "features",
                "component_id": "titanic_title_family_features",
                "component_version": "1.0",
                "config": {"feature_set": "title_family_v1"},
                "inputs": {"dataset": dataset_ref},
            }
        )
        dataset_ref = "features.dataset"
    graph.extend(
        [
            {
                "node_id": "split",
                "component_id": "stratified_holdout",
                "component_version": "1.0",
                "config": {"validation_fraction": 0.2, "seed": 42},
                "inputs": {"dataset": dataset_ref},
            },
            {
                "node_id": "model",
                "component_id": "naive_logistic_classifier",
                "component_version": "1.0",
                "config": {},
                "inputs": {"dataset": dataset_ref, "split": "split.split"},
            },
            {
                "node_id": "evaluation",
                "component_id": "classification_evaluator",
                "component_version": "1.0",
                "config": {"primary_metric": "accuracy"},
                "inputs": {"validation_predictions": "model.validation_predictions"},
            },
        ]
    )
    return [ComponentInvocation.model_validate(node) for node in graph]


if __name__ == "__main__":
    main()
