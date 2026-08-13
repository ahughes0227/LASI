"""Focused tests for the bounded local tool surface."""

from time import sleep

import pytest
from services.contracts import DatasetManifest, DecisionRecord, ExperimentPlan, ToolSpec
from services.contracts.models import DatasetFile, DatasetSample
from services.tools import LocalToolRunner, ToolOutput, ToolRegistry, register_builtin_tools


def _authorization(tool_id: str = "ok") -> tuple[ExperimentPlan, DecisionRecord]:
    plan = ExperimentPlan(
        experiment_plan_id="plan-1",
        project_id="p",
        dataset_version="d",
        hypothesis="h",
        reason_for_experiment="test",
        experiment_type="baseline_probe",
        planned_tool_runs=[{"tool_id": tool_id}],
        execution_backend="local",
        expected_signal="signal",
        success_criteria="pass",
        failure_criteria="fail",
    )
    decision = DecisionRecord(
        decision_id="decision-1",
        project_id="p",
        experiment_plan_id="plan-1",
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="test",
    )
    return plan, decision


def test_registry_checks_versions_and_builtin_inventory() -> None:
    registry = register_builtin_tools(ToolRegistry())

    assert {spec.tool_id for spec in registry.all()} == {
        "dataset_validation",
        "dataset_characterization",
        "baseline",
        "learning_curve",
        "error_analysis",
        "clustering",
        "static_report",
        "component_pipeline",
    }
    assert registry.check_compatibility("baseline", expected_version="1.0").name == "Baseline probe"


def test_local_runner_returns_success_failure_partial_and_terminal_states() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(tool_id="ok", name="ok", version="1"),
        lambda _: ToolOutput(metrics={"x": 1}),
    )
    registry.register(
        ToolSpec(tool_id="partial", name="partial", version="1"),
        lambda _: ToolOutput(partial_success={"what_failed": ["plot"]}),
    )
    registry.register(ToolSpec(tool_id="bad", name="bad", version="1"), lambda _: 1 / 0)
    runner = LocalToolRunner(registry)
    plan, decision = _authorization()

    assert runner.run("ok", "p", "d", plan=plan, decision=decision).status == "succeeded"
    partial_plan, partial_decision = _authorization("partial")
    assert (
        runner.run("partial", "p", "d", plan=partial_plan, decision=partial_decision).status
        == "partial_success"
    )
    bad_plan, bad_decision = _authorization("bad")
    assert runner.run("bad", "p", "d", plan=bad_plan, decision=bad_decision).status == "failed"
    assert (
        runner.run("ok", "p", "d", plan=plan, decision=decision, requested_status="blocked").status
        == "blocked"
    )
    assert (
        runner.run("ok", "p", "d", plan=plan, decision=decision, requested_status="skipped").status
        == "skipped"
    )
    assert (
        runner.run(
            "ok", "p", "d", plan=plan, decision=decision, requested_status="cancelled"
        ).status
        == "cancelled"
    )


def test_local_runner_records_timeout() -> None:
    registry = ToolRegistry()
    registry.register(ToolSpec(tool_id="slow", name="slow", version="1"), lambda _: sleep(0.1))

    plan, decision = _authorization("slow")
    result = LocalToolRunner(registry).run(
        "slow", "p", "d", plan=plan, decision=decision, timeout_seconds=0.001
    )

    assert result.status == "timed_out"
    assert result.failure_reason == "timeout"


def test_dataset_adapters_validate_and_characterize_without_framework_objects() -> None:
    manifest = DatasetManifest(
        project_id="p",
        dataset_version_id="d",
        file_list=[DatasetFile(path="manifest.jsonl")],
        samples=[
            DatasetSample(sample_id="a", label="ok", point_cloud_ref="a.xyz", split="train"),
            DatasetSample(sample_id="b", label="bad", point_cloud_ref="b.xyz", split="test"),
        ],
    )
    registry = register_builtin_tools(ToolRegistry())
    runner = LocalToolRunner(registry)
    validation_plan, validation_decision = _authorization("dataset_validation")
    characterization_plan, characterization_decision = _authorization("dataset_characterization")

    validation = runner.run(
        "dataset_validation",
        "p",
        "d",
        plan=validation_plan,
        decision=validation_decision,
        parameters={"manifest": manifest},
    )
    characterization = runner.run(
        "dataset_characterization",
        "p",
        "d",
        plan=characterization_plan,
        decision=characterization_decision,
        parameters={"manifest": manifest},
    )

    assert validation.status == "succeeded"
    assert characterization.status == "succeeded"
    assert characterization.metrics["sample_size"] == 2


def test_local_runner_rejects_missing_or_mismatched_authorization() -> None:
    registry = ToolRegistry()
    registry.register(ToolSpec(tool_id="ok", name="ok", version="1"), lambda _: ToolOutput())
    plan, decision = _authorization()

    with pytest.raises(PermissionError, match="approved experiment plan"):
        LocalToolRunner(registry).run("other", "p", "d", plan=plan, decision=decision)
    with pytest.raises(PermissionError, match="match"):
        LocalToolRunner(registry).run(
            "ok", "p", "d", plan=plan, decision=decision, experiment_plan_id="other"
        )
