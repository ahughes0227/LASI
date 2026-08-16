"""SQLAlchemy models for LASI operational and outcome memory."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


def utc_now() -> datetime:
    return datetime.now(UTC)


class Record(Base):
    __abstract__ = True
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Project(Record):
    __tablename__ = "projects"
    project_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    problem_type: Mapped[str] = mapped_column(String(255), nullable=False)
    modality: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)


class ResearchAssignmentRecord(Record):
    __tablename__ = "research_assignments"
    assignment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    pause_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_escalation_id: Mapped[str | None] = mapped_column(String(255))
    graph_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(255))
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_wake_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ResearchLoopStateRecord(Record):
    __tablename__ = "research_loop_states"
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    next_phase: Mapped[str | None] = mapped_column(String(64))


class TaskGraphProposalRecord(Record):
    __tablename__ = "task_graph_proposals"
    proposal_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    observed_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class ReasoningRubricRecord(Record):
    __tablename__ = "reasoning_rubrics"
    rubric_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    rubric_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("rubric_id", "version", name="uq_reasoning_rubric_version"),)


class RuntimeTaskRecord(Record):
    __tablename__ = "runtime_tasks"
    task_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("task_graph_proposals.proposal_id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_role: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scientific_checkpoint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rubric_key: Mapped[str] = mapped_column(
        ForeignKey("reasoning_rubrics.rubric_key"), nullable=False
    )
    experiment_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_plans.experiment_plan_id")
    )
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.decision_id"))


class TaskDependencyRecord(Base):
    __tablename__ = "task_dependencies"
    dependency_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    depends_on_task_id: Mapped[str] = mapped_column(
        ForeignKey("runtime_tasks.task_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)


class ContextSnapshotRecord(Record):
    __tablename__ = "context_snapshots"
    context_snapshot_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class TaskAttemptRecord(Record):
    __tablename__ = "task_attempts"
    attempt_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_role: Mapped[str] = mapped_column(String(128), nullable=False)
    lease_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    context_snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    runtime_validation_status: Mapped[str | None] = mapped_column(String(64))


class TaskEventRecord(Base):
    __tablename__ = "task_events"
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("task_attempts.attempt_id"))
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("research_assignments.assignment_id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RubricEvaluationRecord(Record):
    __tablename__ = "rubric_evaluations"
    evaluation_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("task_attempts.attempt_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_status: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_status: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeNodeRecord(Record):
    __tablename__ = "knowledge_nodes"
    node_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"))
    node_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    source_task_id: Mapped[str | None] = mapped_column(ForeignKey("runtime_tasks.task_id"))


class KnowledgeEdgeRecord(Record):
    __tablename__ = "knowledge_edges"
    edge_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"))
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_nodes.node_id"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_nodes.node_id"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class PlannerCatalogNodeRecord(Record):
    """Derived registry node used for planner discovery and traversal."""

    __tablename__ = "planner_catalog_nodes"
    node_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(128))
    lifecycle: Mapped[str] = mapped_column(String(64), nullable=False)


class PlannerCatalogEdgeRecord(Record):
    """Derived typed relationship between planner catalog nodes."""

    __tablename__ = "planner_catalog_edges"
    edge_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("planner_catalog_nodes.node_id"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("planner_catalog_nodes.node_id"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class CriticAssessmentRecord(Record):
    __tablename__ = "critic_assessments"
    assessment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("runtime_tasks.task_id"), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment: Mapped[str] = mapped_column(String(64), nullable=False)
    material: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disposition: Mapped[str] = mapped_column(String(128), nullable=False)


class Dataset(Record):
    __tablename__ = "datasets"
    dataset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255))


class DatasetVersion(Record):
    __tablename__ = "dataset_versions"
    dataset_version_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.dataset_id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    parent_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"), nullable=True
    )
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    benchmark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DatasetCharacterization(Record):
    __tablename__ = "dataset_characterizations"
    characterization_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"), nullable=False
    )
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="complete", nullable=False)


class ExperimentPlan(Record):
    __tablename__ = "experiment_plans"
    experiment_plan_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"), nullable=False
    )
    execution_backend: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ToolRun(Record):
    __tablename__ = "tool_runs"
    tool_run_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    experiment_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_plans.experiment_plan_id"), nullable=True
    )
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id"), nullable=False
    )
    tool_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_backend: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(UTCDateTime())
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ScientistReview(Record):
    __tablename__ = "scientist_reviews"
    review_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    provider_profile_id: Mapped[str] = mapped_column(String(255), nullable=False)
    diagnostic_packet_id: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_diagnosis: Mapped[str] = mapped_column(String(255), nullable=False)
    diagnosis_confidence: Mapped[float] = mapped_column(nullable=False)


class ActionUsage(Base):
    """Immutable operational ledger entry for a metered LASI action."""

    __tablename__ = "action_usage"
    action_usage_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    action_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    metering_status: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_profile_id: Mapped[str | None] = mapped_column(String(255))
    model_name: Mapped[str | None] = mapped_column(String(255))
    reporting_source: Mapped[str | None] = mapped_column(String(255))
    source_reference: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    billed_cost_usd: Mapped[float | None] = mapped_column(Float)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Decision(Record):
    __tablename__ = "decisions"
    decision_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    experiment_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_plans.experiment_plan_id"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Approval(Record):
    __tablename__ = "approvals"
    approval_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.decision_id"), nullable=True
    )
    proposal_id: Mapped[str | None] = mapped_column(String(255))
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Report(Record):
    __tablename__ = "reports"
    report_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    report_state: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(255))


class Outcome(Record):
    __tablename__ = "outcomes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), primary_key=True)
    current_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_date: Mapped[date | None] = mapped_column(Date)
    last_updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )


class OutcomeEvent(Base):
    __tablename__ = "outcome_events"
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(64))
    new_status: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    related_report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.report_id"))
    related_experiment_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiment_plans.experiment_plan_id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Artifact(Record):
    __tablename__ = "artifacts"
    artifact_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"))
    dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.dataset_version_id")
    )
    tool_run_id: Mapped[str | None] = mapped_column(ForeignKey("tool_runs.tool_run_id"))
    scientist_review_id: Mapped[str | None] = mapped_column(
        ForeignKey("scientist_reviews.review_id")
    )
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.decision_id"))
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.report_id"))
    immutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KnowledgeRegistration(Record):
    __tablename__ = "knowledge_registrations"
    document_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id"))
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (UniqueConstraint("path", "git_commit", name="uq_knowledge_path_commit"),)


class Challenge(Record):
    __tablename__ = "challenges"
    challenge_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)


class Prediction(Record):
    __tablename__ = "predictions"
    prediction_artifact_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(ForeignKey("challenges.challenge_id"), nullable=False)
    model_run_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Submission(Record):
    __tablename__ = "submissions"
    submission_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(ForeignKey("challenges.challenge_id"), nullable=False)
    prediction_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("predictions.prediction_artifact_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)


class EvaluationRun(Record):
    __tablename__ = "evaluation_runs"
    evaluation_run_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(ForeignKey("challenges.challenge_id"), nullable=False)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.submission_id"), nullable=False
    )
    evaluator_id: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class EvaluationScore(Record):
    __tablename__ = "evaluation_scores"
    evaluation_result_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.evaluation_run_id"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[float | None] = mapped_column(nullable=True)
