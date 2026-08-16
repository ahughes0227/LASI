"""Compile eligible JSON nodes into planning-only runtime proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from services.contracts import TaskGraphProposal, TaskSpec, WorkflowDefinition

from .roles import resolve_agent_role


class WorkflowCompiler:
    def compile(
        self,
        workflow: WorkflowDefinition,
        *,
        project_id: str,
        assignment_id: str,
        observed_revision: int,
        completed_nodes: set[str] | None = None,
        available_artifacts: set[str] | None = None,
        persisted_plan_ids: set[str] | None = None,
        allowing_decision_ids: set[str] | None = None,
    ) -> TaskGraphProposal:
        completed = completed_nodes or set()
        artifacts = available_artifacts or set()
        plans = persisted_plan_ids or set()
        decisions = allowing_decision_ids or set()
        tasks: list[TaskSpec] = []
        for node in workflow.nodes:
            if node.node_id in completed or not set(node.dependencies).issubset(completed):
                continue
            if node.activation.when != "always" and node.activation.when not in artifacts:
                continue
            if node.task_type in {"experiment_execution", "tool_execution", "component_execution"}:
                if (
                    node.experiment_plan_binding not in plans
                    or node.decision_binding not in decisions
                ):
                    continue
            tasks.append(
                TaskSpec(
                    task_id=f"{workflow.workflow_id}:{node.node_id}:{uuid4().hex[:8]}",
                    project_id=project_id,
                    task_type=node.task_type,
                    agent_role=resolve_agent_role(node),
                    description=f"{workflow.workflow_id}: {node.node_id}",
                    # Dependencies already satisfied by SQL/runtime state are not
                    # re-created as guessed task ids in this proposal.
                    depends_on=[],
                    rubric_id=node.rubric.rubric_id,
                    rubric_version=node.rubric.version,
                    required_inputs=[artifact.artifact_id for artifact in node.reads],
                    required_outputs=[artifact.artifact_id for artifact in node.writes],
                    experiment_plan_id=node.experiment_plan_binding
                    if node.task_type
                    in {"experiment_execution", "tool_execution", "component_execution"}
                    else None,
                    decision_id=node.decision_binding
                    if node.task_type
                    in {"experiment_execution", "tool_execution", "component_execution"}
                    else None,
                    scientific_checkpoint=node.task_type
                    in {"scientific_review", "scientific_critique"},
                    priority=node.priority,
                    max_attempts=node.max_attempts,
                )
            )
        return TaskGraphProposal(
            proposal_id=f"workflow-proposal-{uuid4().hex}",
            assignment_id=assignment_id,
            project_id=project_id,
            observed_revision=observed_revision,
            rationale=f"eligible nodes for {workflow.workflow_id}@{workflow.version}",
            tasks=tasks,
            created_at=datetime.now(UTC),
        )
