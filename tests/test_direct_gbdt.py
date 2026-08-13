"""Synthetic acceptance tests for the direct-horizon GBDT component."""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from services.contracts import ApprovalRecord, DecisionRecord, ExperimentPlan
from services.isolation import IsolationProfile
from services.tools import LocalToolRunner, ToolRegistry, register_direct_horizon_gbdt


def _write_train(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "date", "store_nbr", "family", "sales", "onpromotion"]
        )
        writer.writeheader()
        start = datetime(2020, 1, 1)
        for day in range(45):
            current = start + timedelta(days=day)
            writer.writerow(
                {
                    "id": day + 1,
                    "date": current.date().isoformat(),
                    "store_nbr": 1,
                    "family": "A",
                    "sales": day + 1,
                    "onpromotion": day % 2,
                }
            )


def _approval() -> ApprovalRecord:
    from pathlib import Path

    import yaml

    path = Path("projects/mercury/40_output/approvals/APP-MERCURY-DIRECT-GBDT-COMPONENT-0001.yaml")
    return ApprovalRecord.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _plan(parameters: dict[str, object]) -> tuple[ExperimentPlan, DecisionRecord]:
    plan = ExperimentPlan(
        experiment_plan_id="direct-gbdt-plan",
        project_id="mercury",
        dataset_version="mercury:v1",
        hypothesis="direct model is past-only",
        reason_for_experiment="synthetic test",
        experiment_type="baseline_probe",
        planned_tool_runs=[{"tool_id": "direct_horizon_gbdt", "parameters": parameters}],
        execution_backend="local",
        expected_signal="valid prediction",
        success_criteria="valid outputs",
        failure_criteria="invalid output",
    )
    return plan, DecisionRecord(
        decision_id="direct-gbdt-decision",
        project_id="mercury",
        experiment_plan_id=plan.experiment_plan_id,
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="synthetic only",
    )


def test_direct_gbdt_writes_nonnegative_aligned_validation_predictions(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    output = tmp_path / "output"
    _write_train(train)
    profile = IsolationProfile(
        profile_id="synthetic",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(train),
        "output_dir": str(output),
        "validation_start_date": "2020-02-10",
        "validation_end_date": "2020-02-14",
        "horizon_days": 5,
        "training_window_days": 90,
        "max_rows_per_horizon": 1000,
        "max_iter": 20,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _plan(parameters)
    approval = _approval()
    runner = LocalToolRunner(
        register_direct_horizon_gbdt(ToolRegistry(), approval=approval)
    )
    result = runner.run(
        "direct_horizon_gbdt",
        "mercury",
        "mercury:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "succeeded"
    assert result.metrics["validation_rows"] == 5
    values = (output / "validation_predictions.csv").read_text(encoding="utf-8")
    assert "prediction" in values


def test_direct_gbdt_rejects_duplicate_forecast_ids(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    forecast = tmp_path / "test.csv"
    _write_train(train)
    forecast.write_text(
        "id,date,store_nbr,family,onpromotion\n1,2020-02-15,1,A,0\n1,2020-02-16,1,A,1\n",
        encoding="utf-8",
    )
    profile = IsolationProfile(
        profile_id="synthetic",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(train),
        "forecast_path": str(forecast),
        "output_dir": str(tmp_path / "output"),
        "horizon_days": 5,
        "training_window_days": 90,
        "max_iter": 20,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _plan(parameters)
    approval = _approval()
    registry = register_direct_horizon_gbdt(ToolRegistry(), approval=approval)
    result = LocalToolRunner(registry).run(
        "direct_horizon_gbdt",
        "mercury",
        "mercury:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "failed"
    assert any("IDs must be non-null and unique" in error for error in result.errors)


def test_direct_gbdt_registration_requires_matching_approval(tmp_path: Path) -> None:
    wrong = _approval().model_copy(update={"proposal_id": "other"})

    with pytest.raises(PermissionError, match="does not match durable artifact"):
        register_direct_horizon_gbdt(ToolRegistry(), approval=wrong)


def test_direct_gbdt_rejects_non_authoritative_approval_path(tmp_path: Path) -> None:
    approval = _approval()
    other = tmp_path / "other.yaml"
    other.write_text("approval_id: forged\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="not the authoritative"):
        register_direct_horizon_gbdt(
            ToolRegistry(), approval=approval, approval_path=other
        )


def test_direct_gbdt_test_forecast_uses_submission_schema(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    forecast = tmp_path / "test.csv"
    _write_train(train)
    forecast.write_text(
        "id,date,store_nbr,family,onpromotion\n100,2020-02-15,1,A,0\n",
        encoding="utf-8",
    )
    profile = IsolationProfile(
        profile_id="synthetic",
        allowed_read_paths=(str(tmp_path),),
        allowed_write_paths=(str(tmp_path),),
    )
    parameters: dict[str, object] = {
        "train_path": str(train),
        "forecast_path": str(forecast),
        "output_dir": str(tmp_path / "output"),
        "horizon_days": 5,
        "training_window_days": 90,
        "max_iter": 20,
        "benchmark_protected": True,
        "isolation_profile": profile,
        "isolation_backend": "synthetic-test",
    }
    plan, decision = _plan(parameters)
    approval = _approval()
    registry = register_direct_horizon_gbdt(ToolRegistry(), approval=approval)
    result = LocalToolRunner(registry).run(
        "direct_horizon_gbdt",
        "mercury",
        "mercury:v1",
        plan=plan,
        decision=decision,
        parameters=parameters,
    )

    assert result.status == "succeeded"
    assert (tmp_path / "output" / "submission.csv").read_text(encoding="utf-8").startswith(
        "id,sales\n"
    )
