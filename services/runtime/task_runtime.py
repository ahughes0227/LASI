"""SQL-authoritative task graph, agent handoff, and scientific criticism runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.contracts import (
    AgentResult,
    AgentTask,
    CriticAssessment,
    ProviderTokenUsage,
    ReasoningCriterion,
    ReasoningRubric,
    ResearchAssignment,
    TaskGraphProposal,
    TaskSpec,
    ToolSpec,
)
from services.decisions import DecisionContext, DecisionGate, Recommendation
from services.memory import (
    ActionUsage,
    Artifact,
    ContextSnapshotRecord,
    CriticAssessmentRecord,
    DatasetVersion,
    Decision,
    ExperimentPlan,
    KnowledgeEdgeRecord,
    KnowledgeNodeRecord,
    OperationalMemory,
    ReasoningRubricRecord,
    ResearchAgendaRecord,
    ResearchAssignmentRecord,
    RubricEvaluationRecord,
    RuntimeTaskRecord,
    TaskAttemptRecord,
    TaskDependencyRecord,
    TaskEventRecord,
    TaskGraphProposalRecord,
)


@dataclass(frozen=True, slots=True)
class ProposalIngestionResult:
    proposal_id: str
    accepted: bool
    task_ids: tuple[str, ...]
    rejection_reason: str | None = None


class TaskRuntimeError(ValueError):
    """A task transition is invalid against SQL-authoritative state."""


class TaskRuntimeService:
    """The sole application service for task state, leases, and agent results."""

    def __init__(
        self, memory: OperationalMemory, *, available_tools: tuple[ToolSpec, ...] = ()
    ) -> None:
        self.memory = memory
        self.available_tools = available_tools

    def register_rubric(self, rubric: ReasoningRubric) -> None:
        key = _rubric_key(rubric.rubric_id, rubric.version)
        with self.memory.transaction() as session:
            current = session.get(ReasoningRubricRecord, key)
            if current is not None:
                if current.payload != rubric.model_dump(mode="json"):
                    raise TaskRuntimeError("rubric version is immutable")
                return
            session.add(
                ReasoningRubricRecord(
                    rubric_key=key,
                    rubric_id=rubric.rubric_id,
                    version=rubric.version,
                    capability=rubric.capability,
                    payload=rubric.model_dump(mode="json"),
                )
            )

    def install_default_rubrics(self) -> None:
        for rubric in default_reasoning_rubrics():
            self.register_rubric(rubric)

    def ingest_proposal(self, proposal: TaskGraphProposal) -> ProposalIngestionResult:
        """Record every proposal, accepting valid tasks in the same transaction."""
        with self.memory.transaction() as session:
            return self.ingest_proposal_in_transaction(session, proposal)

    def ingest_proposal_in_transaction(
        self, session: Session, proposal: TaskGraphProposal
    ) -> ProposalIngestionResult:
        """Ingest within a caller-owned transaction so agenda and graph advance atomically."""
        rejection = self._proposal_rejection(session, proposal)
        if session.get(TaskGraphProposalRecord, proposal.proposal_id) is not None:
            raise TaskRuntimeError("task graph proposal id already exists")
        proposal_record = TaskGraphProposalRecord(
            proposal_id=proposal.proposal_id,
            assignment_id=proposal.assignment_id,
            project_id=proposal.project_id,
            observed_revision=proposal.observed_revision,
            status="rejected" if rejection else "accepted",
            rejection_reason=rejection,
            payload=proposal.model_dump(mode="json"),
        )
        session.add(proposal_record)
        session.flush()
        if rejection:
            return ProposalIngestionResult(proposal.proposal_id, False, (), rejection)

        task_ids: list[str] = []
        known = {task.task_id for task in proposal.tasks}
        try:
            for task in proposal.tasks:
                self._validate_task(session, proposal, task, known)
        except TaskRuntimeError as exc:
            proposal_record.status = "rejected"
            proposal_record.rejection_reason = str(exc)
            return ProposalIngestionResult(proposal.proposal_id, False, (), str(exc))
        for sequence, task in enumerate(proposal.tasks):
            session.add(
                RuntimeTaskRecord(
                    task_id=task.task_id,
                    assignment_id=proposal.assignment_id,
                    project_id=task.project_id,
                    proposal_id=proposal.proposal_id,
                    task_type=task.task_type,
                    agent_role=task.agent_role,
                    status="pending" if task.depends_on else "ready",
                    priority=task.priority,
                    sequence=sequence,
                    max_attempts=task.max_attempts,
                    scientific_checkpoint=task.scientific_checkpoint,
                    rubric_key=_rubric_key(task.rubric_id, task.rubric_version),
                    experiment_plan_id=task.experiment_plan_id,
                    decision_id=task.decision_id,
                    payload=task.model_dump(mode="json"),
                )
            )
            task_ids.append(task.task_id)
        session.flush()
        for task in proposal.tasks:
            for dependency in task.depends_on:
                session.add(
                    TaskDependencyRecord(
                        dependency_id=f"{task.task_id}<-{dependency}",
                        task_id=task.task_id,
                        depends_on_task_id=dependency,
                    )
                )
            self._event(
                session,
                runtime_task=session.get(RuntimeTaskRecord, task.task_id),
                event_type="task_accepted",
            )
        self._refresh_ready_tasks(session, proposal.assignment_id)
        return ProposalIngestionResult(proposal.proposal_id, True, tuple(task_ids))

    def lease_ready_task(
        self, assignment_id: str, *, lease_owner: str, lease_seconds: int = 900
    ) -> AgentTask | None:
        """Lease one dependency-satisfied task and create its immutable attempt."""
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            self._recover_expired_leases(session, assignment_id, now)
            self._refresh_ready_tasks(session, assignment_id)
            task_record = session.scalar(
                select(RuntimeTaskRecord)
                .where(
                    RuntimeTaskRecord.assignment_id == assignment_id,
                    RuntimeTaskRecord.status == "ready",
                )
                .order_by(RuntimeTaskRecord.priority.desc(), RuntimeTaskRecord.sequence)
            )
            if task_record is None:
                return None
            task_record.attempt_count += 1
            task_record.status = "leased"
            attempt_id = f"attempt-{uuid4().hex}"
            context_snapshot_id = f"context-{uuid4().hex}"
            expires = now + timedelta(seconds=lease_seconds)
            rubric_record = session.get(ReasoningRubricRecord, task_record.rubric_key)
            assert rubric_record is not None
            task_contract = TaskSpec.model_validate(task_record.payload)
            rubric = ReasoningRubric.model_validate(rubric_record.payload)
            snapshot_payload: dict[str, Any] = {
                "task_id": task_contract.task_id,
                "required_inputs": task_contract.required_inputs,
                "structured_memory_refs": task_contract.structured_memory_refs,
                "icm_role": "minimum_sufficient_context_projection",
                "rubric_key": task_record.rubric_key,
            }
            structured_state = self._structured_state(session, task_contract)
            snapshot_payload["structured_state"] = structured_state
            snapshot_json = json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":"))
            session.add(
                ContextSnapshotRecord(
                    context_snapshot_id=context_snapshot_id,
                    task_id=task_record.task_id,
                    project_id=task_record.project_id,
                    content_hash=hashlib.sha256(snapshot_json.encode()).hexdigest(),
                    payload=snapshot_payload,
                )
            )
            attempt = TaskAttemptRecord(
                attempt_id=attempt_id,
                task_id=task_record.task_id,
                assignment_id=assignment_id,
                project_id=task_record.project_id,
                status="running",
                agent_role=task_record.agent_role,
                lease_owner=lease_owner,
                lease_expires_at=expires,
                context_snapshot_id=context_snapshot_id,
                started_at=now,
                payload={},
            )
            session.add(attempt)
            session.flush()
            self._event(session, task_record, "task_leased", attempt_id=attempt_id)
            return AgentTask(
                assignment_id=assignment_id,
                task=task_contract,
                attempt_id=attempt_id,
                lease_owner=lease_owner,
                lease_expires_at=expires,
                context_snapshot_id=context_snapshot_id,
                rubric=rubric,
                structured_state=structured_state,
            )

    def submit_result(
        self,
        result: AgentResult,
        *,
        lease_owner: str,
        usage: ProviderTokenUsage | None = None,
        raw_response_artifact_ref: str | None = None,
    ) -> str:
        """Validate an agent return, persist it, and advance only accepted SQL state."""
        now = datetime.now(UTC)
        with self.memory.transaction() as session:
            attempt = session.get(TaskAttemptRecord, result.attempt_id)
            if attempt is None or attempt.task_id != result.task_id:
                raise TaskRuntimeError("result does not match a known task attempt")
            if attempt.status != "running" or attempt.lease_owner != lease_owner:
                raise TaskRuntimeError("result does not belong to the active task lease")
            task = session.get(RuntimeTaskRecord, result.task_id)
            assert task is not None
            self._event(
                session,
                task,
                "task_result_received",
                attempt_id=attempt.attempt_id,
            )
            rubric_record = session.get(ReasoningRubricRecord, task.rubric_key)
            assert rubric_record is not None
            rubric = ReasoningRubric.model_validate(rubric_record.payload)
            accepted, validation_reason = self._validate_result(
                session, task, attempt, rubric, result
            )
            if accepted and task.task_type == "orchestration":
                if result.recommended_assignment_status == "continue":
                    if result.task_graph_proposal is None:
                        accepted = False
                        validation_reason = "continuing orchestration requires task_graph_proposal"
                    else:
                        ingestion = self.ingest_proposal_in_transaction(
                            session, result.task_graph_proposal
                        )
                        if not ingestion.accepted:
                            accepted = False
                            validation_reason = ingestion.rejection_reason or "proposal rejected"
                elif result.recommended_assignment_status != "complete":
                    accepted = False
                    validation_reason = "orchestration must recommend continue or complete"

            attempt.finished_at = now
            attempt.duration_seconds = (now - attempt.started_at).total_seconds()
            attempt.runtime_validation_status = "accepted" if accepted else "rejected"
            attempt.status = "succeeded" if accepted else "failed"
            attempt.payload = {
                "result": result.model_dump(mode="json"),
                "raw_response_artifact_ref": raw_response_artifact_ref,
                "validation_reason": validation_reason,
            }
            if accepted:
                task.status = "succeeded"
                self._persist_artifacts_and_claims(session, task, result)
                plan_refs = self._persist_plans_and_decisions(session, task, result)
                task.payload = {
                    **task.payload,
                    "accepted_result": result.model_dump(mode="json"),
                    "plan_and_decision_refs": plan_refs,
                }
                if result.critic_assessment is not None:
                    self._persist_criticism(session, task, result.critic_assessment)
                if task.scientific_checkpoint and result.claims:
                    self._schedule_critics(session, task, result)
                if (
                    task.task_type == "orchestration"
                    and result.recommended_assignment_status == "complete"
                ):
                    self._complete_assignment(session, task.assignment_id, result.summary)
            elif task.attempt_count < task.max_attempts and result.status != "blocked":
                task.status = "ready"
                self._event(
                    session,
                    task,
                    "task_retry_ready",
                    attempt_id=attempt.attempt_id,
                )
            else:
                task.status = "blocked" if result.status == "blocked" else "failed"
            self._record_usage(session, task, attempt, usage)
            self._event(
                session,
                task,
                "task_result_accepted" if accepted else "task_result_rejected",
                attempt_id=attempt.attempt_id,
                payload={"reason": validation_reason},
            )
            self._refresh_ready_tasks(session, task.assignment_id)
            session.flush()
            if task.status in {"succeeded", "failed", "blocked"}:
                self._block_impossible_dependents(session, task.assignment_id)
            if (
                task.status in {"succeeded", "failed", "blocked"}
                and task.task_type != "orchestration"
            ):
                self._schedule_orchestration_if_frontier_closed(session, task)
            return str(task.status)

    def _proposal_rejection(self, session: Session, proposal: TaskGraphProposal) -> str | None:
        agenda = session.scalar(
            select(ResearchAgendaRecord).where(
                ResearchAgendaRecord.assignment_id == proposal.assignment_id
            )
        )
        if agenda is None:
            return "assignment has no research agenda"
        if agenda.project_id != proposal.project_id:
            return "proposal project does not match assignment"
        if agenda.revision != proposal.observed_revision:
            return "proposal was produced from a stale agenda revision"
        ids = [task.task_id for task in proposal.tasks]
        if len(ids) != len(set(ids)):
            return "proposal contains duplicate task ids"
        if self._has_cycle(proposal.tasks):
            return "proposal task graph contains a cycle"
        return None

    @staticmethod
    def _validate_task(
        session: Session,
        proposal: TaskGraphProposal,
        task: TaskSpec,
        known: set[str],
    ) -> None:
        if task.project_id != proposal.project_id:
            raise TaskRuntimeError("task belongs to another project")
        if session.get(RuntimeTaskRecord, task.task_id) is not None:
            raise TaskRuntimeError("task id already exists")
        if (
            session.get(ReasoningRubricRecord, _rubric_key(task.rubric_id, task.rubric_version))
            is None
        ):
            raise TaskRuntimeError("task references an unknown reasoning rubric")
        for dependency in task.depends_on:
            if dependency not in known and session.get(RuntimeTaskRecord, dependency) is None:
                raise TaskRuntimeError("task dependency does not exist")
        if task.task_type in {
            "experiment_execution",
            "tool_execution",
            "component_execution",
        } and (task.experiment_plan_id is None or task.decision_id is None):
            raise TaskRuntimeError("execution task requires persisted plan and decision references")
        if task.experiment_plan_id is not None:
            plan = session.get(ExperimentPlan, task.experiment_plan_id)
            if plan is None or plan.project_id != task.project_id:
                raise TaskRuntimeError("task experiment plan is not persisted")
            decision = session.get(Decision, task.decision_id) if task.decision_id else None
            if decision is None or not decision.allowed:
                raise TaskRuntimeError("task experiment plan lacks its allowing decision")

    @staticmethod
    def _validate_result(
        session: Session,
        task: RuntimeTaskRecord,
        attempt: TaskAttemptRecord,
        rubric: ReasoningRubric,
        result: AgentResult,
    ) -> tuple[bool, str]:
        returned = {item.criterion_id: item for item in result.criterion_results}
        accepted = result.status == "completed"
        reasons: list[str] = []
        if task.scientific_checkpoint and not result.claims:
            accepted = False
            reasons.append("scientific_checkpoint:missing_claims")
        if task.task_type == "scientific_critique" and result.critic_assessment is None:
            accepted = False
            reasons.append("scientific_critique:missing_assessment")
        if result.experiment_plans and task.task_type not in {
            "experiment_planning",
            "falsification_planning",
        }:
            accepted = False
            reasons.append("experiment_plan:return_not_authorized_for_task_type")
        for criterion in rubric.criteria:
            item = returned.get(criterion.criterion_id)
            runtime_status = "accepted"
            if item is None:
                runtime_status = "missing"
            elif criterion.required and item.status != "satisfied":
                runtime_status = "not_satisfied"
            elif criterion.evaluation_mode == "evidentiary" and not item.evidence_refs:
                runtime_status = "missing_evidence"
            if criterion.required and runtime_status != "accepted":
                accepted = False
                reasons.append(f"{criterion.criterion_id}:{runtime_status}")
            session.add(
                RubricEvaluationRecord(
                    evaluation_id=f"{attempt.attempt_id}:{criterion.criterion_id}",
                    attempt_id=attempt.attempt_id,
                    task_id=task.task_id,
                    criterion_id=criterion.criterion_id,
                    agent_status=item.status if item else "missing",
                    runtime_status=runtime_status,
                    payload=item.model_dump(mode="json") if item else {},
                )
            )
        return accepted, ", ".join(reasons) if reasons else "accepted"

    @staticmethod
    def _persist_artifacts_and_claims(
        session: Session, task: RuntimeTaskRecord, result: AgentResult
    ) -> None:
        for item in result.artifacts:
            if session.get(Artifact, item.artifact_id) is None:
                session.add(
                    Artifact(
                        artifact_id=item.artifact_id,
                        artifact_uri=item.uri,
                        artifact_type=item.artifact_type,
                        project_id=task.project_id,
                        immutable=True,
                        payload=item.model_dump(mode="json"),
                    )
                )
        for claim in result.claims:
            if session.get(KnowledgeNodeRecord, claim.claim_id) is None:
                session.add(
                    KnowledgeNodeRecord(
                        node_id=claim.claim_id,
                        project_id=task.project_id,
                        node_type="claim",
                        status=claim.status,
                        source_task_id=task.task_id,
                        payload=claim.model_dump(mode="json"),
                    )
                )
                session.flush()
            for evidence_ref in claim.evidence_refs:
                evidence_node_id = (
                    "evidence:" + hashlib.sha256(evidence_ref.encode()).hexdigest()[:24]
                )
                if session.get(KnowledgeNodeRecord, evidence_node_id) is None:
                    session.add(
                        KnowledgeNodeRecord(
                            node_id=evidence_node_id,
                            project_id=task.project_id,
                            node_type="evidence_reference",
                            status="recorded",
                            source_task_id=task.task_id,
                            payload={"evidence_ref": evidence_ref},
                        )
                    )
                    session.flush()
                edge_id = f"{claim.claim_id}->supported_by->{evidence_node_id}"
                if session.get(KnowledgeEdgeRecord, edge_id) is None:
                    session.add(
                        KnowledgeEdgeRecord(
                            edge_id=edge_id,
                            project_id=task.project_id,
                            source_node_id=claim.claim_id,
                            target_node_id=evidence_node_id,
                            edge_type="supported_by",
                            status="active",
                            payload={},
                        )
                    )

    def _persist_plans_and_decisions(
        self, session: Session, task: RuntimeTaskRecord, result: AgentResult
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for plan in result.experiment_plans:
            if plan.project_id != task.project_id:
                raise TaskRuntimeError("agent returned an experiment plan for another project")
            current = session.get(ExperimentPlan, plan.experiment_plan_id)
            if current is not None:
                if current.payload != plan.model_dump(mode="json"):
                    raise TaskRuntimeError("experiment plan id is immutable")
                decision = session.scalar(
                    select(Decision).where(Decision.experiment_plan_id == plan.experiment_plan_id)
                )
                refs.append(
                    {
                        "experiment_plan_id": plan.experiment_plan_id,
                        "decision_id": decision.decision_id if decision else None,
                        "allowed": decision.allowed if decision else False,
                    }
                )
                continue
            dataset = session.get(DatasetVersion, plan.dataset_version)
            if dataset is None:
                raise TaskRuntimeError("agent plan references an unknown dataset version")
            session.add(
                ExperimentPlan(
                    experiment_plan_id=plan.experiment_plan_id,
                    project_id=plan.project_id,
                    dataset_version_id=plan.dataset_version,
                    execution_backend=plan.execution_backend,
                    approval_required=plan.approval_required,
                    payload=plan.model_dump(mode="json"),
                )
            )
            session.flush()
            decision_contract = DecisionGate().evaluate(
                Recommendation(
                    recommendation_id=f"recommendation-{plan.experiment_plan_id}",
                    project_id=plan.project_id,
                    action=(
                        "run_remote_experiment"
                        if plan.execution_backend != "local"
                        else "run_local_experiment"
                    ),
                    requested_tool_id=(
                        plan.planned_tool_runs[0].tool_id if plan.planned_tool_runs else None
                    ),
                ),
                context=DecisionContext(
                    privacy_mode=plan.privacy_mode,
                    available_tools=self.available_tools,
                    dataset_status=dataset.status,
                    now=datetime.now(UTC),
                ),
                plan=plan,
            )
            session.add(
                Decision(
                    decision_id=decision_contract.decision_id,
                    project_id=decision_contract.project_id,
                    experiment_plan_id=decision_contract.experiment_plan_id,
                    decision=decision_contract.decision,
                    allowed=decision_contract.allowed,
                    approval_required=decision_contract.approval_required,
                    payload=decision_contract.model_dump(mode="json"),
                )
            )
            self._record_not_applicable(
                session,
                project_id=task.project_id,
                action_id=plan.experiment_plan_id,
                action_type="experiment_plan_persistence",
            )
            self._record_not_applicable(
                session,
                project_id=task.project_id,
                action_id=decision_contract.decision_id,
                action_type="decision_evaluation",
            )
            refs.append(
                {
                    "experiment_plan_id": plan.experiment_plan_id,
                    "decision_id": decision_contract.decision_id,
                    "allowed": decision_contract.allowed,
                }
            )
        return refs

    @staticmethod
    def _structured_state(session: Session, task: TaskSpec) -> dict[str, dict[str, Any]]:
        state: dict[str, dict[str, Any]] = {}
        references = [
            *task.required_inputs,
            *task.structured_memory_refs,
            *([task.experiment_plan_id] if task.experiment_plan_id else []),
            *([task.decision_id] if task.decision_id else []),
        ]
        for reference in references:
            for model, kind in (
                (RuntimeTaskRecord, "task"),
                (ExperimentPlan, "experiment_plan"),
                (Decision, "decision"),
                (KnowledgeNodeRecord, "knowledge_node"),
                (Artifact, "artifact"),
            ):
                record = session.get(model, reference)
                if record is not None:
                    state[reference] = {
                        "record_type": kind,
                        "payload": record.payload,
                    }
                    break
        return state

    def _schedule_critics(
        self, session: Session, source_task: RuntimeTaskRecord, result: AgentResult
    ) -> None:
        proposal_id = f"runtime-critic-{source_task.task_id}"
        if session.get(TaskGraphProposalRecord, proposal_id) is None:
            session.add(
                TaskGraphProposalRecord(
                    proposal_id=proposal_id,
                    assignment_id=source_task.assignment_id,
                    project_id=source_task.project_id,
                    observed_revision=0,
                    status="runtime_generated",
                    payload={"source_task_id": source_task.task_id},
                )
            )
            session.flush()
        for offset, claim in enumerate(result.claims, start=1):
            task_id = f"critic:{claim.claim_id}"
            if session.get(RuntimeTaskRecord, task_id) is not None:
                continue
            spec = TaskSpec(
                task_id=task_id,
                project_id=source_task.project_id,
                task_type="scientific_critique",
                agent_role="scientific-critic",
                description=(
                    f"Try to disprove claim {claim.claim_id}; identify validity threats, "
                    "alternative explanations, and discriminating falsification tests."
                ),
                depends_on=[source_task.task_id],
                rubric_id="scientific-critic",
                rubric_version="1.0",
                required_inputs=[claim.claim_id, *claim.evidence_refs],
                required_outputs=["critic_assessment"],
                priority=source_task.priority + 10,
            )
            session.add(
                RuntimeTaskRecord(
                    task_id=task_id,
                    assignment_id=source_task.assignment_id,
                    project_id=source_task.project_id,
                    proposal_id=proposal_id,
                    task_type=spec.task_type,
                    agent_role=spec.agent_role,
                    status="pending",
                    priority=spec.priority,
                    sequence=source_task.sequence + offset,
                    max_attempts=spec.max_attempts,
                    scientific_checkpoint=False,
                    rubric_key=_rubric_key(spec.rubric_id, spec.rubric_version),
                    payload=spec.model_dump(mode="json"),
                )
            )
            session.flush()
            session.add(
                TaskDependencyRecord(
                    dependency_id=f"{task_id}<-{source_task.task_id}",
                    task_id=task_id,
                    depends_on_task_id=source_task.task_id,
                )
            )
            self._event(session, session.get(RuntimeTaskRecord, task_id), "critic_task_created")

    @staticmethod
    def _schedule_orchestration_if_frontier_closed(
        session: Session, source_task: RuntimeTaskRecord
    ) -> None:
        open_task = session.scalar(
            select(RuntimeTaskRecord).where(
                RuntimeTaskRecord.assignment_id == source_task.assignment_id,
                RuntimeTaskRecord.status.in_(("pending", "ready", "leased")),
            )
        )
        if open_task is not None:
            return
        task_id = f"orchestrate:{source_task.task_id}"
        proposal_id = f"runtime-{task_id}"
        if session.get(RuntimeTaskRecord, task_id) is not None:
            return
        session.add(
            TaskGraphProposalRecord(
                proposal_id=proposal_id,
                assignment_id=source_task.assignment_id,
                project_id=source_task.project_id,
                observed_revision=0,
                status="runtime_generated",
                payload={"frontier_source_task_id": source_task.task_id},
            )
        )
        session.flush()
        spec = TaskSpec(
            task_id=task_id,
            project_id=source_task.project_id,
            task_type="orchestration",
            agent_role="lasi-coordinator",
            description=(
                "Assess the completed frontier and either propose the next evidence-ordered "
                "task graph or recommend assignment completion."
            ),
            depends_on=[source_task.task_id],
            rubric_id="orchestrator-planning",
            rubric_version="1.0",
            required_inputs=[source_task.task_id],
            required_outputs=["task_graph_proposal_or_completion"],
            priority=100,
        )
        session.add(
            RuntimeTaskRecord(
                task_id=task_id,
                assignment_id=source_task.assignment_id,
                project_id=source_task.project_id,
                proposal_id=proposal_id,
                task_type=spec.task_type,
                agent_role=spec.agent_role,
                status="ready",
                priority=spec.priority,
                sequence=source_task.sequence + 1,
                max_attempts=spec.max_attempts,
                scientific_checkpoint=False,
                rubric_key=_rubric_key(spec.rubric_id, spec.rubric_version),
                payload=spec.model_dump(mode="json"),
            )
        )
        session.flush()
        session.add(
            TaskDependencyRecord(
                dependency_id=f"{task_id}<-{source_task.task_id}",
                task_id=task_id,
                depends_on_task_id=source_task.task_id,
            )
        )
        TaskRuntimeService._event(
            session, session.get(RuntimeTaskRecord, task_id), "orchestration_task_created"
        )

    @staticmethod
    def _complete_assignment(session: Session, assignment_id: str, summary: str) -> None:
        record = session.get(ResearchAssignmentRecord, assignment_id)
        if record is None:
            raise TaskRuntimeError("assignment disappeared during completion")
        now = datetime.now(UTC)
        contract = ResearchAssignment.model_validate(record.payload).model_copy(
            update={"status": "completed", "latest_summary": summary, "updated_at": now}
        )
        record.status = "completed"
        record.payload = contract.model_dump(mode="json")

    def _persist_criticism(
        self,
        session: Session,
        task: RuntimeTaskRecord,
        assessment: CriticAssessment,
    ) -> None:
        claim = session.get(KnowledgeNodeRecord, assessment.claim_id)
        if claim is None:
            raise TaskRuntimeError("critic assessment references an unknown claim")
        session.add(
            CriticAssessmentRecord(
                assessment_id=assessment.assessment_id,
                project_id=task.project_id,
                task_id=task.task_id,
                claim_id=assessment.claim_id,
                assessment=assessment.assessment,
                material=assessment.material,
                disposition=assessment.recommended_disposition,
                payload=assessment.model_dump(mode="json"),
            )
        )
        critique_node = f"critique:{assessment.assessment_id}"
        session.add(
            KnowledgeNodeRecord(
                node_id=critique_node,
                project_id=task.project_id,
                node_type="critique",
                status="accepted",
                source_task_id=task.task_id,
                payload=assessment.model_dump(mode="json"),
            )
        )
        session.flush()
        session.add(
            KnowledgeEdgeRecord(
                edge_id=f"{critique_node}->criticizes->{assessment.claim_id}",
                project_id=task.project_id,
                source_node_id=critique_node,
                target_node_id=assessment.claim_id,
                edge_type="criticizes",
                status="active",
                payload={},
            )
        )
        claim.status = _claim_status(assessment)
        claim.payload = {**claim.payload, "status": claim.status}
        if assessment.material and assessment.falsification_tests:
            self._schedule_falsification_planning(session, task, assessment)

    @staticmethod
    def _schedule_falsification_planning(
        session: Session,
        critic_task: RuntimeTaskRecord,
        assessment: CriticAssessment,
    ) -> None:
        task_id = f"falsify:{assessment.assessment_id}"
        if session.get(RuntimeTaskRecord, task_id) is not None:
            return
        proposal_id = f"runtime-falsify-{assessment.assessment_id}"
        session.add(
            TaskGraphProposalRecord(
                proposal_id=proposal_id,
                assignment_id=critic_task.assignment_id,
                project_id=critic_task.project_id,
                observed_revision=0,
                status="runtime_generated",
                payload={"assessment_id": assessment.assessment_id},
            )
        )
        session.flush()
        spec = TaskSpec(
            task_id=task_id,
            project_id=critic_task.project_id,
            task_type="falsification_planning",
            agent_role="experiment-engineer",
            description="Plan the cheapest material test that can resolve the critic's challenge.",
            depends_on=[critic_task.task_id],
            rubric_id="falsification-planning",
            rubric_version="1.0",
            required_inputs=[assessment.assessment_id, assessment.claim_id],
            required_outputs=["experiment_plan"],
            priority=critic_task.priority + 5,
        )
        session.add(
            RuntimeTaskRecord(
                task_id=task_id,
                assignment_id=critic_task.assignment_id,
                project_id=critic_task.project_id,
                proposal_id=proposal_id,
                task_type=spec.task_type,
                agent_role=spec.agent_role,
                status="pending",
                priority=spec.priority,
                sequence=critic_task.sequence + 1,
                max_attempts=spec.max_attempts,
                scientific_checkpoint=False,
                rubric_key=_rubric_key(spec.rubric_id, spec.rubric_version),
                payload=spec.model_dump(mode="json"),
            )
        )
        session.flush()
        session.add(
            TaskDependencyRecord(
                dependency_id=f"{task_id}<-{critic_task.task_id}",
                task_id=task_id,
                depends_on_task_id=critic_task.task_id,
            )
        )
        TaskRuntimeService._event(
            session, session.get(RuntimeTaskRecord, task_id), "falsification_task_created"
        )

    @staticmethod
    def _record_usage(
        session: Session,
        task: RuntimeTaskRecord,
        attempt: TaskAttemptRecord,
        usage: ProviderTokenUsage | None,
    ) -> None:
        session.add(
            ActionUsage(
                action_usage_id=f"usage-{attempt.attempt_id}",
                project_id=task.project_id,
                action_id=attempt.attempt_id,
                action_type=f"agent_task:{task.task_type}",
                metering_status="reported" if usage else "not_available",
                reporting_source=usage.reporting_source if usage else None,
                source_reference=usage.source_reference if usage else None,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                cached_input_tokens=usage.cached_input_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                billed_cost_usd=usage.billed_cost_usd if usage else None,
                unavailable_reason=(
                    None if usage else "agent runtime did not return an authoritative usage receipt"
                ),
                reported_at=usage.reported_at if usage else None,
                payload=usage.model_dump(mode="json") if usage else {},
            )
        )

    @staticmethod
    def _record_not_applicable(
        session: Session, *, project_id: str, action_id: str, action_type: str
    ) -> None:
        session.add(
            ActionUsage(
                action_usage_id=f"usage-{action_id}",
                project_id=project_id,
                action_id=action_id,
                action_type=action_type,
                metering_status="not_applicable",
                unavailable_reason="deterministic runtime action does not invoke a model",
                payload={},
            )
        )

    @staticmethod
    def _refresh_ready_tasks(session: Session, assignment_id: str) -> None:
        pending = list(
            session.scalars(
                select(RuntimeTaskRecord).where(
                    RuntimeTaskRecord.assignment_id == assignment_id,
                    RuntimeTaskRecord.status == "pending",
                )
            )
        )
        for task in pending:
            dependency_ids = list(
                session.scalars(
                    select(TaskDependencyRecord.depends_on_task_id).where(
                        TaskDependencyRecord.task_id == task.task_id
                    )
                )
            )
            dependencies = [session.get(RuntimeTaskRecord, item) for item in dependency_ids]
            if dependencies and all(
                item is not None and item.status == "succeeded" for item in dependencies
            ):
                task.status = "ready"
                TaskRuntimeService._event(session, task, "task_ready")

    @staticmethod
    def _block_impossible_dependents(session: Session, assignment_id: str) -> None:
        pending = list(
            session.scalars(
                select(RuntimeTaskRecord).where(
                    RuntimeTaskRecord.assignment_id == assignment_id,
                    RuntimeTaskRecord.status == "pending",
                )
            )
        )
        changed = True
        while changed:
            changed = False
            for task in pending:
                if task.status != "pending":
                    continue
                dependency_ids = list(
                    session.scalars(
                        select(TaskDependencyRecord.depends_on_task_id).where(
                            TaskDependencyRecord.task_id == task.task_id
                        )
                    )
                )
                dependencies = [session.get(RuntimeTaskRecord, item) for item in dependency_ids]
                if any(
                    item is not None and item.status in {"failed", "blocked"}
                    for item in dependencies
                ):
                    task.status = "blocked"
                    task.payload = {
                        **task.payload,
                        "runtime_block_reason": "dependency_failed_or_blocked",
                    }
                    TaskRuntimeService._event(
                        session,
                        task,
                        "task_blocked_by_dependency",
                        payload={"reason": "dependency_failed_or_blocked"},
                    )
                    changed = True

    @staticmethod
    def _recover_expired_leases(session: Session, assignment_id: str, now: datetime) -> None:
        attempts = list(
            session.scalars(
                select(TaskAttemptRecord).where(
                    TaskAttemptRecord.assignment_id == assignment_id,
                    TaskAttemptRecord.status == "running",
                    TaskAttemptRecord.lease_expires_at < now,
                )
            )
        )
        for attempt in attempts:
            attempt.status = "expired"
            attempt.finished_at = now
            task = session.get(RuntimeTaskRecord, attempt.task_id)
            if task is not None and task.status == "leased":
                task.status = "ready" if task.attempt_count < task.max_attempts else "failed"
                TaskRuntimeService._event(
                    session,
                    task,
                    "task_lease_expired",
                    attempt_id=attempt.attempt_id,
                    payload={"next_status": task.status},
                )

    @staticmethod
    def _event(
        session: Session,
        runtime_task: RuntimeTaskRecord | None,
        event_type: str,
        *,
        attempt_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        assert runtime_task is not None
        session.add(
            TaskEventRecord(
                event_id=f"task-event-{uuid4().hex}",
                task_id=runtime_task.task_id,
                attempt_id=attempt_id,
                assignment_id=runtime_task.assignment_id,
                project_id=runtime_task.project_id,
                event_type=event_type,
                payload=payload or {},
            )
        )

    @staticmethod
    def _has_cycle(tasks: list[TaskSpec]) -> bool:
        graph = {
            task.task_id: [dep for dep in task.depends_on if dep in {t.task_id for t in tasks}]
            for task in tasks
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(child) for child in graph[node]):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)


def default_reasoning_rubrics() -> tuple[ReasoningRubric, ...]:
    return (
        ReasoningRubric(
            rubric_id="orchestrator-planning",
            version="1.0",
            capability="orchestration",
            purpose="Turn unresolved scientific questions into an evidence-ordered task graph.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="separate_observation_inference",
                    instruction="Separate observed evidence from inference and recommendation.",
                ),
                ReasoningCriterion(
                    criterion_id="smallest_discriminating_next_step",
                    instruction="Prefer the smallest task that distinguishes live hypotheses.",
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="scientific-critic",
            version="1.0",
            capability="critique",
            purpose="Try to disprove material claims and expose hidden performance regressions.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="strongest_counterargument",
                    instruction="State the strongest evidence-linked counterargument.",
                ),
                ReasoningCriterion(
                    criterion_id="validity_threats",
                    instruction=(
                        "Check leakage, metric integrity, segment regressions, confounding, "
                        "and reproducibility."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="falsification_test",
                    instruction=(
                        "Give a concrete discriminating test for every material unresolved "
                        "challenge."
                    ),
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="falsification-planning",
            version="1.0",
            capability="experiment_planning",
            purpose="Plan the cheapest valid experiment that can resolve a material criticism.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="competing_predictions",
                    instruction=(
                        "State expected outcomes under the claim and its strongest alternative."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="plan_persisted",
                    instruction=(
                        "Return a persisted ExperimentPlan reference with success and failure "
                        "criteria."
                    ),
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="scientific-exploration",
            version="1.0",
            capability="exploration",
            purpose=(
                "Characterize observations and anomalies without prematurely "
                "prescribing a solution."
            ),
            criteria=[
                ReasoningCriterion(
                    criterion_id="data_quality_checked",
                    instruction=(
                        "Identify missing, malformed, incomparable, or leakage-prone evidence."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="observation_inference_separated",
                    instruction="Label direct observations separately from interpretations.",
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="scientist-reasoning",
            version="1.0",
            capability="scientific_review",
            purpose="Generate falsifiable explanations from experimental evidence.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="observed_vs_expected",
                    instruction="Compare the observed result with the plan's expected signal.",
                ),
                ReasoningCriterion(
                    criterion_id="alternative_hypotheses",
                    instruction=(
                        "State credible competing explanations and their supporting evidence."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="discriminating_test",
                    instruction="Recommend the smallest test that distinguishes live explanations.",
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="experiment-planning",
            version="1.0",
            capability="experiment_planning",
            purpose="Turn one hypothesis into a feasible, discriminating ExperimentPlan.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="competing_predictions",
                    instruction="Define different expected outcomes under competing hypotheses.",
                ),
                ReasoningCriterion(
                    criterion_id="feasibility_checked",
                    instruction=(
                        "Verify required data, tools, backend, budget, and expected artifacts."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="plan_persisted",
                    instruction="Return the persisted plan and allowing decision references.",
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="experiment-execution",
            version="1.0",
            capability="experiment_execution",
            purpose="Execute exactly one approved plan and preserve complete evidence.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="authorization_matches",
                    instruction=(
                        "Confirm task, plan, dataset, decision, tool, and backend references match."
                    ),
                    evaluation_mode="deterministic",
                ),
                ReasoningCriterion(
                    criterion_id="artifacts_complete",
                    instruction="Return every expected artifact or an explicit structured failure.",
                ),
                ReasoningCriterion(
                    criterion_id="observed_signal_recorded",
                    instruction="Record the result without adding an unsupported mechanism claim.",
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="result-review",
            version="1.0",
            capability="result_review",
            purpose="Interpret performance, expose regressions, and create falsifiable claims.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="metric_integrity",
                    instruction=(
                        "Check evaluation population, comparator, metric, and missing predictions."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="segment_regressions",
                    instruction=(
                        "Check whether aggregate gains conceal important segment regressions."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="claims_falsifiable",
                    instruction=(
                        "State claims with evidence, uncertainty, and invalidation conditions."
                    ),
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="knowledge-curation",
            version="1.0",
            capability="knowledge_curating",
            purpose="Propose governed semantic memory without promoting uncertain claims.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="knowledge_type_preserved",
                    instruction=(
                        "Keep observations, hypotheses, lessons, facts, and policies distinct."
                    ),
                ),
                ReasoningCriterion(
                    criterion_id="contradictions_preserved",
                    instruction=(
                        "Link supporting and contradicting evidence rather than erasing either."
                    ),
                ),
            ],
        ),
        ReasoningRubric(
            rubric_id="static-reporting",
            version="1.0",
            capability="reporting",
            purpose="Render a fixed report from accepted structured state and artifacts.",
            criteria=[
                ReasoningCriterion(
                    criterion_id="required_sections_rendered",
                    instruction="Render every fixed section, including explicit missing states.",
                    evaluation_mode="deterministic",
                ),
                ReasoningCriterion(
                    criterion_id="provenance_complete",
                    instruction=(
                        "Reference plans, attempts, decisions, criticisms, outcomes, and artifacts."
                    ),
                ),
            ],
        ),
    )


def _rubric_key(rubric_id: str, version: str) -> str:
    return f"{rubric_id}@{version}"


def _claim_status(assessment: CriticAssessment) -> str:
    if assessment.recommended_disposition in {"refute", "refute_or_reframe"}:
        return "refuted"
    if assessment.recommended_disposition in {"accept", "survived_challenge"}:
        return "survived_challenge"
    return "challenged"
