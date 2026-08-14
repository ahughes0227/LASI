"""Wave 5B end-to-end fixture tests.

The point clouds are generated as small binary NPZ assets at test time. No
external provider, remote host, or industrial data is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as parquet
import pytest
from services.contracts import (
    ApprovalRecord,
    DecisionRecord,
    DiagnosticPacket,
    EvaluationPolicy,
    ExperimentPlan,
    ProviderProfile,
    StaticReportData,
    ToolRunResult,
    ToolSpec,
)
from services.contracts.models import BudgetEstimate, DatasetManifest, ReportSection
from services.datasets import (
    characterize_dataset,
    create_dataset_version,
    load_parquet_manifest,
    validate_dataset,
)
from services.decisions import DecisionContext, DecisionGate, Recommendation
from services.experiments import assemble_diagnostic_packet, compile_plan, require_allowed_decision
from services.memory import (
    Approval,
    Base,
    Decision,
    OperationalMemory,
    Project,
    create_engine,
    create_session_factory,
)
from services.outcomes import OutcomeService
from services.providers import (
    MemoryArtifactSink,
    MockResponseMode,
    MockScientistProvider,
    ProviderValidationError,
)
from services.reports import ReportRenderer
from services.tools import LocalToolRunner, ToolOutput, ToolRegistry

PROJECT_ID = "wave5b-point-cloud-fixture"
DATASET_ID = "synthetic_scratch_pointcloud"
VERSION_ID = f"{DATASET_ID}:v0.1.0"


@pytest.fixture
def point_cloud_fixture(tmp_path: Path) -> tuple[Path, DatasetManifest]:
    """Create public synthetic binary clouds and their Parquet manifest."""
    np.savez(
        tmp_path / "scratch-a.npz",
        points=np.asarray([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=np.float32),
    )
    np.savez(
        tmp_path / "non-scratch-a.npz",
        points=np.asarray([[0, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32),
    )
    manifest_path = tmp_path / "manifest.parquet"
    parquet.write_table(
        pa.table(
            {
                "sample_id": ["scratch-a", "non-scratch-a"],
                "label": ["scratch", "non_scratch"],
                "point_cloud_ref": ["scratch-a.npz", "non-scratch-a.npz"],
                "split": ["train", "test"],
            }
        ),
        manifest_path,
    )
    manifest = load_parquet_manifest(
        manifest_path,
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        dataset_version_id=VERSION_ID,
        label_schema={"labels": ["scratch", "non_scratch"]},
    )
    return tmp_path, manifest


def _tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            tool_id="baseline",
            name="Synthetic baseline",
            version="1.0",
            supported_execution_backends=["local"],
        ),
        lambda context: ToolOutput(output_refs=["metrics://baseline"], metrics={"f1": 0.75}),
    )
    registry.register(
        ToolSpec(
            tool_id="failing-tool",
            name="Synthetic failure",
            version="1.0",
            supported_execution_backends=["local"],
        ),
        lambda context: (_ for _ in ()).throw(RuntimeError("synthetic tool failure")),
    )
    registry.register(
        ToolSpec(
            tool_id="partial-tool",
            name="Synthetic partial",
            version="1.0",
            supported_execution_backends=["local"],
        ),
        lambda context: ToolOutput(
            output_refs=["metrics://partial"],
            partial_success={
                "what_succeeded": ["metrics"],
                "what_failed": ["plot"],
                "missing_artifacts": ["plot.png"],
                "can_continue": True,
            },
        ),
    )
    return registry


def _plan(tool_id: str = "baseline"):
    return compile_plan(
        {
            "project_id": PROJECT_ID,
            "dataset_version": VERSION_ID,
            "hypothesis": "A bounded baseline establishes the evidence floor.",
            "experiment_type": "baseline_probe",
            "planned_tool_runs": [{"tool_id": tool_id}],
            "expected_artifacts": ["metrics.json"],
            "budget_estimate": {"cpu_hours": 1},
        },
        tool_registry=_tools().all(),
    ).plan


def _decision(plan, *, action: str = "run_local_experiment", **kwargs):
    return DecisionGate().evaluate(
        Recommendation("recommendation-1", PROJECT_ID, action),
        context=DecisionContext(
            dataset_status="validated",
            available_budget=BudgetEstimate(cpu_hours=2),
            available_tools=_tools().all(),
            **kwargs,
        ),
        plan=plan,
    )


def _authorized_run(
    tool_id: str, *, input_refs: list[str] | None = None
) -> tuple[ToolRunResult, ExperimentPlan, DecisionRecord]:
    """Run a fixture tool through the current plan and decision gates."""
    tools = _tools()
    plan = _plan(tool_id)
    decision = _decision(plan)
    assert decision.allowed
    require_allowed_decision(plan, decision)
    result = LocalToolRunner(tools).run(
        tool_id,
        PROJECT_ID,
        VERSION_ID,
        plan=plan,
        decision=decision,
        input_refs=input_refs,
        experiment_plan_id=plan.experiment_plan_id,
    )
    return result, plan, decision


def _report(status: str = "pending") -> StaticReportData:
    def section(summary: str = "fixture evidence") -> ReportSection:
        return ReportSection(section_status="complete", summary=summary)

    return StaticReportData(
        report_id="report-wave5b-1",
        report_header={"project_id": PROJECT_ID, "title": "Wave 5B fixture"},
        executive_summary=section(),
        current_decision=section(),
        dataset_summary=section(),
        dataset_characterization=section(),
        eda_findings=section(),
        surprising_findings=section(),
        proposed_approaches=section(),
        experiment_summary=section(),
        experiments_tried=section(),
        results_and_interpretation=section(),
        model_comparison=section(),
        performance_gap_diagnosis=section(),
        learning_curves=section(),
        error_analysis=section(),
        cluster_or_latent_analysis=section(),
        scientist_review=section(),
        scientific_criticism=section(),
        decision_record=section(),
        knowledge_context=section(),
        recommendation=section(),
        project_outcome=section(status),
        token_telemetry=section(),
        appendix=section(),
        project_outcome_status=status,
    )


def test_complete_workflow_from_binary_fixture_to_report(
    point_cloud_fixture: tuple[Path, DatasetManifest], tmp_path: Path
) -> None:
    root, manifest = point_cloud_fixture
    validation = validate_dataset(manifest, root)
    assert validation.valid and validation.samples_checked == 2
    approval = ApprovalRecord(
        approval_id="approval-wave5b-dataset",
        project_id=PROJECT_ID,
        action_type="create_dataset_version",
        risk_level="high",
        requested_by="wave5b",
        approved_by="fixture-reviewer",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )
    version = create_dataset_version(
        manifest,
        manifest_path=root / "manifest.parquet",
        created_by="wave5b",
        approval=approval,
    )
    assert version.comparability_status == "unknown"
    characterization = characterize_dataset(
        manifest, root, characterization_id="characterization-1"
    )
    assert characterization.status == "complete"

    plan = _plan()
    decision = _decision(plan)
    assert decision.allowed
    require_allowed_decision(plan, decision)
    run = LocalToolRunner(_tools()).run(
        "baseline",
        PROJECT_ID,
        VERSION_ID,
        plan=plan,
        decision=decision,
        input_refs=[str(root / "manifest.parquet")],
        experiment_plan_id=plan.experiment_plan_id,
    )
    assert run.status == "succeeded" and run.metrics["f1"] == 0.75

    packet = assemble_diagnostic_packet(
        diagnostic_packet_id="packet-wave5b-1",
        project_id=PROJECT_ID,
        problem_type="binary_classification",
        dataset_version_id=VERSION_ID,
        privacy_mode="summary_only_to_scientist",
        dataset_characterization_summary="Two public synthetic NPZ point clouds validated.",
        evaluation_policy=EvaluationPolicy(policy_id="eval-1", primary_metric="f1"),
        tool_results=[run],
        allowed_recommendation_types=["run_error_analysis"],
    )
    provider = MockScientistProvider(
        ProviderProfile(
            provider_id="mock-wave5b",
            provider_type="mock_provider",
            model_name="fixture",
            privacy_capabilities=["summary_only_to_scientist"],
        ),
        artifact_sink=MemoryArtifactSink(),
    )
    review = provider.review(packet, experiment_ids=[plan.experiment_plan_id])
    assert review.raw_response_artifact and review.project_id == PROJECT_ID
    report_path = ReportRenderer().write_immutable(_report(), tmp_path / "report.html")
    assert "Wave 5B fixture" in report_path.read_text(encoding="utf-8")


def test_dataset_validation_failure_and_tool_failure(
    point_cloud_fixture: tuple[Path, DatasetManifest],
) -> None:
    root, manifest = point_cloud_fixture
    np.savez(root / "scratch-a.npz", points=np.ones((2, 2), dtype=np.float32))
    validation = validate_dataset(manifest, root)
    assert not validation.valid and any("coordinates" in error for error in validation.errors)
    failed, _, _ = _authorized_run("failing-tool")
    assert failed.status == "failed" and failed.failure_reason == "tool_error"


def test_partial_success_is_structured(point_cloud_fixture: tuple[Path, DatasetManifest]) -> None:
    run, _, _ = _authorized_run("partial-tool")
    assert run.status == "partial_success"
    assert run.partial_success == {
        "what_succeeded": ["metrics"],
        "what_failed": ["plot"],
        "missing_artifacts": ["plot.png"],
        "can_continue": True,
    }


def test_approval_privacy_and_non_comparable_blocks() -> None:
    plan = _plan()
    approval = _decision(plan, action="modify_labels")
    assert approval.decision == "convert_to_proposal" and not approval.allowed
    privacy = _decision(
        plan,
        action="send_thumbnails",
        privacy_mode="summary_only_to_scientist",
        provider_privacy_capabilities=("thumbnails_allowed",),
    )
    assert privacy.decision == "block" and privacy.blocked_by == ["privacy"]
    comparison = _decision(plan, dataset_comparable=False)
    assert comparison.decision == "block" and "comparability" in comparison.blocked_by


def test_invalid_provider_response_and_stop_recommendation(
    point_cloud_fixture: tuple[Path, DatasetManifest],
) -> None:
    packet = DiagnosticPacket(
        diagnostic_packet_id="packet-wave5b-2",
        project_id=PROJECT_ID,
        problem_type="binary_classification",
        dataset_version_id=VERSION_ID,
        privacy_mode="summary_only_to_scientist",
        allowed_recommendation_types=["stop_low_expected_value", "run_error_analysis"],
    )
    profile = ProviderProfile(
        provider_id="mock-wave5b",
        provider_type="mock_provider",
        model_name="fixture",
        privacy_capabilities=["summary_only_to_scientist"],
    )
    with pytest.raises(ProviderValidationError):
        MockScientistProvider(profile, mode=MockResponseMode.MALFORMED_RESPONSE).review(packet)
    stop = MockScientistProvider(profile, mode=MockResponseMode.STOP_RECOMMENDATION).review(packet)
    assert stop.stop_recommendation == "low_expected_value"
    decision = DecisionGate().evaluate(
        Recommendation("stop-1", PROJECT_ID, "stop_project"), context=DecisionContext()
    )
    assert decision.decision == "stop_project" and not decision.allowed


def test_outcome_transition_history_is_append_only() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    memory.add(
        Project(
            project_id=PROJECT_ID,
            project_name="Wave 5B",
            problem_type="binary_classification",
            modality="point_cloud",
        )
    )
    memory.add(
        Decision(
            decision_id="decision-wave5b-deployment",
            project_id=PROJECT_ID,
            decision="allow",
            allowed=True,
            payload={"action_requested": "deployment"},
        )
    )
    memory.add(
        Approval(
            approval_id="approval-wave5b-deployment",
            project_id=PROJECT_ID,
            decision_id="decision-wave5b-deployment",
            action_type="deployment",
            approval_status="approved",
        )
    )
    service = OutcomeService(memory, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    service.transition(
        PROJECT_ID,
        "deployed",
        reason="fixture validation passed",
        owner="wave5b",
        decision_id="decision-wave5b-deployment",
        approval_id="approval-wave5b-deployment",
    )
    service.transition(
        PROJECT_ID,
        "failed_in_production",
        reason="synthetic domain shift",
        owner="wave5b",
        evidence=["artifact://monitoring/synthetic"],
        decision_id="decision-wave5b-deployment",
        approval_id="approval-wave5b-deployment",
    )
    assert service.current(PROJECT_ID).current_status == "failed_in_production"
    assert [(event.previous_status, event.new_status) for event in service.events(PROJECT_ID)] == [
        (None, "deployed"),
        ("deployed", "failed_in_production"),
    ]
