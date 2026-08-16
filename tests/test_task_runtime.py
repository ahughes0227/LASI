"""End-to-end tests for SQL task handoffs, rubrics, criticism, and telemetry."""

from pathlib import Path

from services.admin import AssignmentAdminService, open_admin_service
from services.contracts import (
    AgentResult,
    CriterionResult,
    CriticAssessment,
    ExperimentPlan,
    FalsificationTest,
    ProviderTokenUsage,
    ReasoningCriterion,
    ReasoningRubric,
    ResearchLoopPolicy,
    ScientificClaim,
    TaskGraphProposal,
    TaskSpec,
    ValidityThreat,
)
from services.memory import (
    ActionUsage,
    Artifact,
    ContextSnapshotRecord,
    CriticAssessmentRecord,
    Dataset,
    DatasetVersion,
    Decision,
    KnowledgeEdgeRecord,
    KnowledgeNodeRecord,
    Project,
    RuntimeTaskRecord,
    TaskAttemptRecord,
    TaskEventRecord,
    TaskGraphProposalRecord,
)
from services.memory import (
    ExperimentPlan as ExperimentPlanRecord,
)
from services.runtime import TaskRuntimeService
from services.tools import ToolRegistry, register_builtin_tools


def _admin(tmp_path: Path) -> AssignmentAdminService:
    return open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )


def _assignment(admin: AssignmentAdminService) -> str:
    return admin.start(
        project_id="semantic-project",
        objective="derive experiment-validated semantic knowledge",
        loop_policy=ResearchLoopPolicy(objective_metric="rmsle", objective_direction="minimize"),
        launch_worker=False,
    ).assignment.assignment_id


def _satisfied(*criterion_ids: str) -> list[CriterionResult]:
    return [
        CriterionResult(
            criterion_id=criterion_id,
            status="satisfied",
            evidence_refs=[f"sql:evidence:{criterion_id}"],
        )
        for criterion_id in criterion_ids
    ]


def test_runtime_owns_task_graph_handoffs_and_schedules_constant_criticism(
    tmp_path: Path,
) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    admin.memory.add(
        Dataset(
            dataset_id="semantic-dataset",
            project_id="semantic-project",
            name="semantic dataset",
            payload={},
        )
    )
    admin.memory.add(
        DatasetVersion(
            dataset_version_id="semantic-dataset:v1",
            dataset_id="semantic-dataset",
            project_id="semantic-project",
            version="v1",
            data_hash="abc123",
            status="validated",
            payload={},
        )
    )
    tools = register_builtin_tools(ToolRegistry())
    runtime = TaskRuntimeService(admin.memory, available_tools=tools.all())
    runtime.register_rubric(
        ReasoningRubric(
            rubric_id="result-analysis",
            version="1.0",
            capability="scientific_review",
            purpose="Interpret results while separating evidence from inference.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="observed_vs_expected",
                    instruction="Compare observed and expected signals.",
                )
            ],
        )
    )

    planning = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert planning is not None
    snapshot = admin.memory.get(ContextSnapshotRecord, planning.context_snapshot_id)
    assert snapshot is not None
    assert snapshot.payload["icm_role"] == "minimum_sufficient_context_projection"
    proposal = TaskGraphProposal(
        proposal_id="proposal-semantic-001",
        assignment_id=assignment_id,
        project_id="semantic-project",
        observed_revision=1,
        rationale="Analyze the current experimental result before further implementation.",
        tasks=[
            TaskSpec(
                task_id="task-result-analysis",
                project_id="semantic-project",
                task_type="result_analysis",
                agent_role="scientist-reviewer",
                description="Interpret segment-level performance and form falsifiable claims.",
                rubric_id="result-analysis",
                rubric_version="1.0",
                required_outputs=["claims"],
                scientific_checkpoint=True,
            )
        ],
    )
    assert (
        runtime.submit_result(
            AgentResult(
                task_id=planning.task.task_id,
                attempt_id=planning.attempt_id,
                status="completed",
                summary="Proposed the evidence-analysis frontier.",
                criterion_results=_satisfied(
                    "separate_observation_inference", "smallest_discriminating_next_step"
                ),
                task_graph_proposal=proposal,
                recommended_assignment_status="continue",
            ),
            lease_owner="runtime-1",
        )
        == "succeeded"
    )

    analysis = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert analysis is not None
    assert analysis.task.task_id == "task-result-analysis"
    usage = ProviderTokenUsage(
        reporting_source="test-runtime-receipt",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
    )
    assert (
        runtime.submit_result(
            AgentResult(
                task_id=analysis.task.task_id,
                attempt_id=analysis.attempt_id,
                status="completed",
                summary="Performance appears concentrated in one segment.",
                criterion_results=_satisfied("observed_vs_expected"),
                claims=[
                    ScientificClaim(
                        claim_id="claim-segment-mechanism",
                        statement="The improvement is caused by zero-target handling.",
                        status="experimentally_supported",
                        confidence=0.7,
                        evidence_refs=["artifact:error-analysis#target-regimes"],
                    )
                ],
            ),
            lease_owner="runtime-1",
            usage=usage,
        )
        == "succeeded"
    )

    critic = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert critic is not None
    assert critic.task.task_type == "scientific_critique"
    assessment = CriticAssessment(
        assessment_id="critique-segment-mechanism",
        claim_id="claim-segment-mechanism",
        assessment="not_supported",
        strongest_counterargument="Zero-target rows do not account for most total error.",
        confidence=0.9,
        material=True,
        validity_threats=[
            ValidityThreat(
                threat_type="mechanism_mismatch",
                severity="high",
                description="Aggregate improvement is not localized to the claimed regime.",
                evidence_refs=["artifact:error-analysis#target-regimes"],
            )
        ],
        falsification_tests=[
            FalsificationTest(
                test_id="test-zero-contribution",
                description="Compare candidate and baseline error by zero/positive regime.",
                supports_claim_when="Improvement is concentrated in zero targets.",
                refutes_claim_when="Positive-target improvement is equal or larger.",
            )
        ],
        recommended_disposition="refute_or_reframe",
        evidence_refs=["artifact:error-analysis#target-regimes"],
    )
    assert (
        runtime.submit_result(
            AgentResult(
                task_id=critic.task.task_id,
                attempt_id=critic.attempt_id,
                status="completed",
                summary="The claimed mechanism does not survive criticism.",
                criterion_results=_satisfied(
                    "strongest_counterargument", "validity_threats", "falsification_test"
                ),
                critic_assessment=assessment,
            ),
            lease_owner="runtime-1",
        )
        == "succeeded"
    )

    falsification = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert falsification is not None
    assert falsification.task.task_type == "falsification_planning"
    plan = ExperimentPlan(
        experiment_plan_id="plan-falsify-segment-mechanism",
        project_id="semantic-project",
        dataset_version="semantic-dataset:v1",
        hypothesis="The claimed zero-target mechanism explains the improvement.",
        reason_for_experiment="Discriminate the claim from positive-target alternatives.",
        experiment_type="error_analysis",
        planned_tool_runs=[{"tool_id": "error_analysis"}],
        execution_backend="local",
        expected_signal="Improvement is concentrated in zero-target rows.",
        success_criteria="Zero-target improvement exceeds positive-target improvement.",
        failure_criteria="Positive-target improvement is equal or larger.",
    )
    assert (
        runtime.submit_result(
            AgentResult(
                task_id=falsification.task.task_id,
                attempt_id=falsification.attempt_id,
                status="completed",
                summary="Persisted the cheapest discriminating error-analysis plan.",
                criterion_results=_satisfied("competing_predictions", "plan_persisted"),
                experiment_plans=[plan],
            ),
            lease_owner="runtime-1",
        )
        == "succeeded"
    )
    assert admin.memory.get(ExperimentPlanRecord, plan.experiment_plan_id)
    decisions = admin.memory.list_for_project(Decision, "semantic-project")
    plan_decision = next(
        item for item in decisions if item.experiment_plan_id == plan.experiment_plan_id
    )
    assert plan_decision.allowed
    orchestration = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")
    assert orchestration is not None
    assert orchestration.task.task_type == "orchestration"
    source_state = orchestration.structured_state[falsification.task.task_id]["payload"]
    assert source_state["plan_and_decision_refs"][0]["allowed"] is True
    assert admin.memory.get(KnowledgeNodeRecord, "claim-segment-mechanism").status == "refuted"
    assert admin.memory.get(CriticAssessmentRecord, assessment.assessment_id)
    assert admin.memory.list_for_project(KnowledgeEdgeRecord, "semantic-project")
    recorded_usage = admin.memory.get(ActionUsage, f"usage-{analysis.attempt_id}")
    assert recorded_usage is not None
    assert recorded_usage.total_tokens == 200
    assert admin.memory.list_for_project(TaskEventRecord, "semantic-project")
    assert admin.memory.list_for_project(TaskAttemptRecord, "semantic-project")


def _dataset(admin: AssignmentAdminService, project_id: str = "semantic-project") -> str:
    admin.memory.add(
        Dataset(
            dataset_id=f"{project_id}-dataset",
            project_id=project_id,
            name="semantic dataset",
            payload={},
        )
    )
    admin.memory.add(
        DatasetVersion(
            dataset_version_id=f"{project_id}-dataset:v1",
            dataset_id=f"{project_id}-dataset",
            project_id=project_id,
            version="v1",
            data_hash="abc123",
            status="validated",
            payload={},
        )
    )
    return f"{project_id}-dataset:v1"


def test_task_is_rejected_when_its_decision_authorizes_another_plan(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    dataset_version_id = _dataset(admin)
    runtime = TaskRuntimeService(admin.memory)
    for plan_id in ("plan-authorized", "plan-requested"):
        admin.memory.add(
            ExperimentPlanRecord(
                experiment_plan_id=plan_id,
                project_id="semantic-project",
                dataset_version_id=dataset_version_id,
                execution_backend="local",
                payload={},
            )
        )
    admin.memory.add(
        Decision(
            decision_id="decision-authorized",
            project_id="semantic-project",
            experiment_plan_id="plan-authorized",
            decision="allow",
            allowed=True,
            payload={},
        )
    )
    proposal = TaskGraphProposal(
        proposal_id="proposal-borrowed-authorization",
        assignment_id=assignment_id,
        project_id="semantic-project",
        observed_revision=1,
        rationale="Execute the requested plan under another plan's allowing decision.",
        tasks=[
            TaskSpec(
                task_id="must-not-run",
                project_id="semantic-project",
                task_type="experiment_execution",
                agent_role="experiment-engineer",
                description="Run the requested plan.",
                rubric_id="experiment-execution",
                rubric_version="1.0",
                experiment_plan_id="plan-requested",
                decision_id="decision-authorized",
            )
        ],
    )

    result = runtime.ingest_proposal(proposal)

    assert not result.accepted
    assert result.rejection_reason == "task experiment plan lacks its allowing decision"
    assert admin.memory.get(RuntimeTaskRecord, "must-not-run") is None


def test_leased_context_excludes_records_from_other_projects(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    admin.memory.add(
        Project(
            project_id="other-project",
            project_name="other project",
            problem_type="unknown",
            modality="unknown",
        )
    )
    for project_id in ("semantic-project", "other-project"):
        admin.memory.add(
            Artifact(
                artifact_id=f"artifact-{project_id}",
                artifact_uri=f"sql:artifact:{project_id}",
                artifact_type="analysis",
                project_id=project_id,
                payload={"project_id": project_id},
            )
        )
    proposal = TaskGraphProposal(
        proposal_id="proposal-cross-project-read",
        assignment_id=assignment_id,
        project_id="semantic-project",
        observed_revision=1,
        rationale="Read this project's evidence while naming another project's artifact.",
        tasks=[
            TaskSpec(
                task_id="task-context-projection",
                project_id="semantic-project",
                task_type="result_analysis",
                agent_role="scientist-reviewer",
                description="Interpret the analysis artifacts referenced by this task.",
                rubric_id="result-review",
                rubric_version="1.0",
                structured_memory_refs=[
                    "artifact-semantic-project",
                    "artifact-other-project",
                ],
                priority=200,
            )
        ],
    )
    assert runtime.ingest_proposal(proposal).accepted

    leased = runtime.lease_ready_task(assignment_id, lease_owner="runtime-1")

    assert leased is not None
    assert leased.task.task_id == "task-context-projection"
    assert "artifact-semantic-project" in leased.structured_state
    assert "artifact-other-project" not in leased.structured_state
    snapshot = admin.memory.get(ContextSnapshotRecord, leased.context_snapshot_id)
    assert "artifact-other-project" not in snapshot.payload["structured_state"]


def test_stale_task_graph_is_recorded_but_never_becomes_executable(tmp_path: Path) -> None:
    admin = _admin(tmp_path)
    assignment_id = _assignment(admin)
    runtime = TaskRuntimeService(admin.memory)
    proposal = TaskGraphProposal(
        proposal_id="stale-proposal",
        assignment_id=assignment_id,
        project_id="semantic-project",
        observed_revision=99,
        rationale="stale state",
        tasks=[
            TaskSpec(
                task_id="must-not-run",
                project_id="semantic-project",
                task_type="experiment_execution",
                agent_role="experiment-engineer",
                description="This task was proposed from stale state.",
                rubric_id="falsification-planning",
                rubric_version="1.0",
            )
        ],
    )

    result = runtime.ingest_proposal(proposal)

    assert not result.accepted
    assert "stale" in (result.rejection_reason or "")
    assert admin.memory.get(TaskGraphProposalRecord, proposal.proposal_id).status == "rejected"
    assert admin.memory.get(RuntimeTaskRecord, "must-not-run") is None
