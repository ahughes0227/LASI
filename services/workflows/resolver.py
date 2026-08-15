"""Structural deduplication for workflow build requests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from services.contracts import (
    Provenance,
    WorkflowCandidate,
    WorkflowDefinition,
    WorkflowResolution,
)

from .registry import WorkflowRegistry


class WorkflowResolver:
    """Resolve REUSE, COMPOSE, EXTEND, or NEW before workflow authoring."""

    def __init__(self, registry: WorkflowRegistry) -> None:
        self.registry = registry

    def resolve(self, requested: WorkflowDefinition) -> WorkflowResolution:
        existing = self.registry.all()
        candidates = [self._compare(requested, item) for item in existing]
        candidates.sort(key=lambda item: item.overall_score, reverse=True)
        same_id = next(
            (item for item in candidates if item.workflow_id == requested.workflow_id), None
        )
        if same_id is not None and same_id.version != requested.version:
            return self._result(
                requested,
                "extend",
                candidates,
                [same_id.workflow_id],
                same_id.missing_requirements,
                "The requested version extends an existing workflow responsibility.",
            )
        exact = next(
            (
                item
                for item in candidates
                if item.task_coverage == 1
                and item.artifact_coverage == 1
                and item.gate_coverage == 1
            ),
            None,
        )
        if exact is not None:
            return self._result(
                requested,
                "reuse",
                candidates,
                [exact.workflow_id],
                [],
                "An installed workflow satisfies the requested graph contract.",
            )

        compatible = [item for item in candidates if item.task_coverage > 0]
        covered: set[str] = set()
        selected: list[str] = []
        requested_tasks = {node.task_type for node in requested.nodes}
        for candidate in compatible:
            existing_workflow = self.registry.get(candidate.workflow_id, candidate.version)
            contribution = {node.task_type for node in existing_workflow.nodes} - covered
            if contribution:
                selected.append(candidate.workflow_id)
                covered.update(contribution)
            if requested_tasks.issubset(covered):
                break
        if len(selected) > 1 and requested_tasks.issubset(covered):
            return self._result(
                requested,
                "compose",
                candidates,
                selected,
                [],
                "Multiple installed workflows cover the requested task types when composed.",
            )

        if same_id is not None:
            return self._result(
                requested,
                "extend",
                candidates,
                [same_id.workflow_id],
                same_id.missing_requirements,
                "The requested workflow extends an existing workflow responsibility.",
            )

        missing = [
            f"task_type:{node.task_type}"
            for node in requested.nodes
            if not any(
                node.task_type == existing_node.task_type
                for item in existing
                for existing_node in item.nodes
            )
        ]
        return self._result(
            requested,
            "new",
            candidates,
            [],
            missing,
            "No existing workflow or composition satisfies the requested graph contract.",
        )

    @staticmethod
    def _compare(requested: WorkflowDefinition, existing: WorkflowDefinition) -> WorkflowCandidate:
        requested_tasks = {node.task_type for node in requested.nodes}
        existing_tasks = {node.task_type for node in existing.nodes}
        requested_artifacts = {
            artifact.artifact_id
            for node in requested.nodes
            for artifact in [*node.reads, *node.writes]
        }
        existing_artifacts = {
            artifact.artifact_id
            for node in existing.nodes
            for artifact in [*node.reads, *node.writes]
        }
        requested_gates = {
            node.decision_gate.gate_id for node in requested.nodes if node.decision_gate
        }
        existing_gates = {
            node.decision_gate.gate_id for node in existing.nodes if node.decision_gate
        }
        task_coverage = _coverage(requested_tasks, existing_tasks)
        artifact_coverage = _coverage(requested_artifacts, existing_artifacts)
        gate_coverage = _coverage(requested_gates, existing_gates)
        score = task_coverage * 0.6 + artifact_coverage * 0.2 + gate_coverage * 0.2
        missing = [f"task_type:{item}" for item in sorted(requested_tasks - existing_tasks)]
        return WorkflowCandidate(
            workflow_id=existing.workflow_id,
            version=existing.version,
            task_coverage=task_coverage,
            artifact_coverage=artifact_coverage,
            gate_coverage=gate_coverage,
            overall_score=round(score, 6),
            missing_requirements=missing,
        )

    @staticmethod
    def _result(
        requested: WorkflowDefinition,
        action: str,
        candidates: list[WorkflowCandidate],
        selected: list[str],
        missing: list[str],
        rationale: str,
    ) -> WorkflowResolution:
        return WorkflowResolution(
            resolution_id=f"workflow-resolution-{uuid4().hex}",
            requested_workflow_id=requested.workflow_id,
            action=action,
            candidates=candidates,
            selected_workflow_ids=selected,
            missing_requirements=missing,
            rationale=rationale,
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[requested.workflow_id]),
        )


def _coverage(required: set[str], available: set[str]) -> float:
    if not required:
        return 1.0
    return len(required & available) / len(required)
