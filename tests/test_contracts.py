"""Conformance tests for the canonical LASI contracts."""

import pytest
from pydantic import ValidationError

from lasi.contracts import (
    CONTRACTS,
    DatasetManifest,
    ExperimentPlan,
    ProjectConfig,
    StaticReportData,
    contract_json_schema,
    validate_contract,
    validate_contract_json,
)


def test_every_contract_has_strict_schema_and_version() -> None:
    assert len(CONTRACTS) == 28
    for contract in CONTRACTS.values():
        schema = contract_json_schema(contract)
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "schema_version" in schema["properties"]
        assert schema["properties"]["schema_version"]["default"] == "1.0"


def test_unknown_fields_are_rejected_at_each_nested_boundary() -> None:
    with pytest.raises(ValidationError):
        ProjectConfig(
            project_id="p1",
            project_name="Scratch",
            problem_type="classification",
            modality="point_cloud",
            unexpected="nope",
        )

    with pytest.raises(ValidationError):
        DatasetManifest(
            project_id="p1",
            dataset_version_id="d1",
            file_list=[{"path": "data.jsonl", "unexpected": True}],
        )


def test_json_schema_validation_path_uses_the_same_contract() -> None:
    plan = validate_contract(
        ExperimentPlan,
        {
            "experiment_plan_id": "plan-1",
            "project_id": "p1",
            "dataset_version": "dataset:v1",
            "hypothesis": "more data helps",
            "reason_for_experiment": "diagnosis",
            "experiment_type": "baseline_probe",
            "execution_backend": "local",
            "expected_signal": "recall increases",
            "success_criteria": "recall >= 0.8",
            "failure_criteria": "recall remains flat",
        },
    )
    assert plan.schema_version == "1.0"
    assert plan.dataset_version == "dataset:v1"
    assert (
        validate_contract_json(ExperimentPlan, plan.model_dump_json()).experiment_plan_id
        == "plan-1"
    )

    with pytest.raises(ValidationError):
        validate_contract(ExperimentPlan, {"project_id": "p1"})


def test_existing_template_field_names_remain_readable_without_weakening_contract() -> None:
    plan = ExperimentPlan(
        experiment_plan_id="plan-1",
        project_id="p1",
        dataset_version="dataset:v1",
        hypothesis="h",
        reason_for_experiment="r",
        experiment_type="baseline_probe",
        planned_tool_runs=[{"tool": "characterize", "run_id": "run-1"}],
        execution_backend="local",
        expected_signal="signal",
        success_criteria="pass",
        failure_criteria="fail",
        approval_required=False,
    )
    assert plan.planned_tool_runs[0].tool_id == "characterize"


def test_report_contract_requires_all_fixed_sections() -> None:
    section = {"section_status": "not_run"}
    fields = {
        "report_id": "report-1",
        "report_header": {"project_id": "p1"},
        "project_outcome_status": "pending",
        "provenance": {},
    }
    for name in StaticReportData.model_fields:
        if name not in fields and name not in {"schema_version", "report_state"}:
            fields[name] = section
    report = StaticReportData(**fields)
    assert report.project_outcome.section_status == "not_run"
