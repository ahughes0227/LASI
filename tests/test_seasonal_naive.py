"""Synthetic-fixture tests for the trusted seasonal-naive baseline."""

import csv
from pathlib import Path

import pytest
from services.contracts import ApprovalRecord, DecisionRecord, ExperimentPlan
from services.experiments import experiment_plan_content_hash
from services.isolation import BenchmarkIsolationError, IsolationProfile
from services.tools import LocalToolRunner, ToolRegistry, register_seasonal_naive_baseline


def _write_panel(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "store_nbr", "family", "sales"])
        writer.writeheader()
        for day, sales in enumerate(range(1, 9), start=1):
            writer.writerow(
                {"date": f"2020-01-{day:02d}", "store_nbr": "1", "family": "A", "sales": sales}
            )


def _authorization(parameters: dict[str, object]) -> tuple[ExperimentPlan, DecisionRecord]:
    plan = ExperimentPlan(
        experiment_plan_id="plan-seasonal",
        project_id="project",
        dataset_version="dataset:v1",
        hypothesis="seasonal naive is a valid reference",
        reason_for_experiment="synthetic acceptance test",
        experiment_type="baseline_probe",
        planned_tool_runs=[{"tool_id": "seasonal_naive_baseline", "parameters": parameters}],
        execution_backend="local",
        expected_signal="complete artifact set",
        success_criteria="finite output",
        failure_criteria="validation failure",
    )
    decision = DecisionRecord(
        decision_id="decision-seasonal",
        project_id="project",
        experiment_plan_id=plan.experiment_plan_id,
        experiment_plan_hash=experiment_plan_content_hash(plan),
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="synthetic test only",
    )
    return plan, decision


def _toolbox_approval() -> ApprovalRecord:
    return ApprovalRecord(
        approval_id="APP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001",
        project_id="mercury",
        proposal_id="PROP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001",
        action_type="update_toolbox",
        risk_level="high",
        requested_by="operator",
        approved_by="reviewer",
        approval_status="approved",
        created_at="2026-08-13T00:00:00Z",
    )


def test_seasonal_naive_uses_only_prior_history_and_writes_artifacts(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    output = tmp_path / "output"
    _write_panel(panel)
    profile = IsolationProfile(
        profile_id="synthetic-benchmark",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "output_dir": str(output),
        "holdout_start_date": "2020-01-08",
        "holdout_end_date": "2020-01-08",
        "seasonal_lag_days": 7,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)
    registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
    result = LocalToolRunner(registry).run(
        "seasonal_naive_baseline",
        "project",
        "dataset:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "succeeded"
    assert result.metrics["seasonal_lag_count"] == 1
    assert result.metrics["rmsle"] > 0.0
    assert (output / "validation_predictions.csv").is_file()
    assert (output / "metrics.json").is_file()


def test_seasonal_naive_rejects_non_allowlisted_benchmark_paths(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    _write_panel(panel)
    profile = IsolationProfile(
        profile_id="synthetic-benchmark",
        allowed_read_paths=(str(tmp_path / "allowed"),),
        allowed_write_paths=(str(tmp_path / "allowed"),),
    )
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "output_dir": str(tmp_path / "output"),
        "holdout_start_date": "2020-01-08",
        "holdout_end_date": "2020-01-08",
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)
    registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
    result = LocalToolRunner(registry).run(
        "seasonal_naive_baseline",
        "project",
        "dataset:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "failed"
    assert result.failure_reason == "tool_error"
    assert any("outside benchmark allowlist" in error for error in result.errors)


def test_seasonal_naive_rejects_invalid_profile_at_runner_boundary(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    _write_panel(panel)
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "output_dir": str(tmp_path / "output"),
        "holdout_start_date": "2020-01-08",
        "holdout_end_date": "2020-01-08",
        "benchmark_protected": True,
        "isolation_profile": IsolationProfile(profile_id="unsafe", network="allow"),
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)

    with pytest.raises(BenchmarkIsolationError, match="preflight failed"):
        registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
        LocalToolRunner(registry).run(
            "seasonal_naive_baseline",
            "project",
            "dataset:v1",
            plan=plan,
            decision=decision,
            parameters=parameters,
        )


def test_seasonal_naive_registration_requires_toolbox_approval() -> None:
    denied = _toolbox_approval().model_copy(update={"approval_status": "pending"})

    with pytest.raises(PermissionError, match="seasonal-naive toolbox"):
        register_seasonal_naive_baseline(ToolRegistry(), approval=denied)

    unrelated = _toolbox_approval().model_copy(update={"proposal_id": "other"})
    with pytest.raises(PermissionError, match="seasonal-naive toolbox"):
        register_seasonal_naive_baseline(ToolRegistry(), approval=unrelated)

    unrelated_id = _toolbox_approval().model_copy(update={"approval_id": "other"})
    with pytest.raises(PermissionError, match="seasonal-naive toolbox"):
        register_seasonal_naive_baseline(ToolRegistry(), approval=unrelated_id)


def test_seasonal_naive_does_not_leak_earlier_holdout_labels(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    output = tmp_path / "output"
    _write_panel(panel)
    profile = IsolationProfile(
        profile_id="synthetic-benchmark",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "output_dir": str(output),
        "holdout_start_date": "2020-01-07",
        "holdout_end_date": "2020-01-08",
        "seasonal_lag_days": 1,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)
    registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
    result = LocalToolRunner(registry).run(
        "seasonal_naive_baseline",
        "project",
        "dataset:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    predictions = output / "validation_predictions.csv"
    prediction_lines = predictions.read_text(encoding="utf-8").splitlines()
    assert result.status == "succeeded"
    assert prediction_lines[-1].endswith(",6.0")


def test_seasonal_naive_writes_test_schema_without_reading_test_labels(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    forecast = tmp_path / "test.csv"
    output = tmp_path / "output"
    _write_panel(panel)
    forecast.write_text(
        "id,date,store_nbr,family,onpromotion\n9,2020-01-09,1,A,0\n",
        encoding="utf-8",
    )
    profile = IsolationProfile(
        profile_id="synthetic-benchmark",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "forecast_path": str(forecast),
        "output_dir": str(output),
        "seasonal_lag_days": 7,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)
    registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
    result = LocalToolRunner(registry).run(
        "seasonal_naive_baseline",
        "project",
        "dataset:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "succeeded"
    assert (output / "submission.csv").read_text(encoding="utf-8").splitlines()[0] == "id,sales"


def test_recursive_seasonal_uses_only_prior_predictions_after_holdout_start(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    output = tmp_path / "output"
    _write_panel(panel)
    profile = IsolationProfile(
        profile_id="synthetic-benchmark",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(panel),
        "output_dir": str(output),
        "holdout_start_date": "2020-01-07",
        "holdout_end_date": "2020-01-08",
        "seasonal_lag_days": 1,
        "recursive_seasonal": True,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _authorization(parameters)
    registry = register_seasonal_naive_baseline(ToolRegistry(), approval=_toolbox_approval())
    result = LocalToolRunner(registry).run(
        "seasonal_naive_baseline",
        "project",
        "dataset:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    predictions = (output / "validation_predictions.csv").read_text(encoding="utf-8").splitlines()
    assert result.status == "succeeded"
    assert predictions[-1].endswith(",6.0")
