"""Durable vertical-slice tests for the authoritative diagnostic workflow."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from services.contracts import (
    ApprovalRecord,
    DatasetManifest,
    ProjectConfig,
    ProviderProfile,
)
from services.contracts.models import DatasetFile, DatasetSample
from services.core.artifacts import MlflowArtifactStore
from services.memory import (
    ActionUsage,
    Approval,
    Artifact,
    Base,
    DatasetVersion,
    Decision,
    KnowledgeRegistration,
    OperationalMemory,
    Report,
    ScientistReview,
    ToolRun,
    create_engine,
    create_session_factory,
)
from services.providers import MockScientistProvider
from services.tools import ToolRegistry, register_builtin_tools
from services.workflows import DiagnosticWorkflowRequest, run_diagnostic_workflow


def test_diagnostic_workflow_persists_every_handoff(tmp_path: Path) -> None:
    np.savez(tmp_path / "sample.npz", points=np.asarray([[0, 0, 0], [1, 0, 0]], dtype=np.float32))
    manifest = DatasetManifest(
        project_id="workflow-project",
        dataset_id="workflow-dataset",
        dataset_version_id="workflow-dataset:v1",
        file_list=[DatasetFile(path="sample.npz")],
        samples=[
            DatasetSample(
                sample_id="sample-1",
                label="scratch",
                point_cloud_ref="sample.npz",
                split="test",
            )
        ],
        label_schema={"labels": ["scratch"]},
        provenance={"source_path": str(tmp_path / "manifest.parquet")},
    )
    project = ProjectConfig(
        project_id="workflow-project",
        project_name="Durable workflow",
        problem_type="binary_classification",
        modality="point_cloud",
        privacy_mode="summary_only_to_scientist",
    )
    approval = ApprovalRecord(
        approval_id="approval-workflow-dataset",
        project_id=project.project_id,
        action_type="create_dataset_version",
        risk_level="high",
        requested_by="test",
        approved_by="reviewer",
        approval_status="approved",
        created_at=datetime.now(UTC),
    )
    registry = register_builtin_tools(ToolRegistry())
    provider = MockScientistProvider(
        ProviderProfile(
            provider_id="workflow-mock",
            provider_type="mock_provider",
            model_name="deterministic",
            privacy_capabilities=["summary_only_to_scientist"],
        )
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))

    result = run_diagnostic_workflow(
        DiagnosticWorkflowRequest(
            project=project,
            manifest=manifest,
            dataset_root=tmp_path,
            dataset_approval=approval,
            tool_registry=registry,
            provider=provider,
            artifact_store=MlflowArtifactStore(tmp_path / "mlruns"),
            report_path=tmp_path / "report.html",
            knowledge_path=tmp_path / "knowledge" / "lessons" / "workflow.md",
            icm_root=tmp_path / "icm",
        ),
        memory,
    )

    assert result.report_path.is_file()
    assert memory.get(Approval, approval.approval_id)
    assert memory.get(DatasetVersion, result.dataset_version_id)
    assert memory.get(ToolRun, result.tool_run_id)
    assert memory.get(ScientistReview, result.scientist_review_id)
    usage_records = memory.list_for_project(ActionUsage, project.project_id)
    review_usage = next(
        record for record in usage_records if record.action_id == result.scientist_review_id
    )
    assert len(usage_records) == 11
    assert review_usage.metering_status == "not_available"
    assert review_usage.total_tokens is None
    assert memory.get(Report, result.report_id)
    assert memory.get(KnowledgeRegistration, result.knowledge_proposal_id)
    assert len(memory.list_for_project(Decision, project.project_id)) == 2
    assert len(memory.list_for_project(Artifact, project.project_id)) == 2
    assert memory.get(Report, result.report_id).artifact_id
    assert memory.outcome_events(project.project_id)
    project_icm = tmp_path / "icm" / "projects" / project.project_id
    assert (project_icm / "10_context/dataset_profile.md").is_file()
    assert list((project_icm / "20_work/experiments").glob("*/results.md"))
    assert (project_icm / "40_output/recommendation.md").is_file()
    assert (project_icm / "40_output/limitations.md").is_file()
    assert (project_icm / "30_evidence/claims").is_dir()
