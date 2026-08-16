"""Fail-closed validation for declarative JSON workflow packages."""

from __future__ import annotations

from collections import defaultdict, deque

from services.contracts import WorkflowDefinition

from .roles import AgentRoleRoutingError, resolve_agent_role


class WorkflowValidationError(ValueError):
    """A workflow package cannot be installed or compiled."""


def validate_workflow(
    workflow: WorkflowDefinition,
    *,
    skills: set[str],
    capabilities: set[str],
    prompts: set[tuple[str, str]],
    rubrics: set[tuple[str, str]],
    profiles: set[tuple[str, str]],
) -> WorkflowDefinition:
    errors: list[str] = []
    nodes = {node.node_id: node for node in workflow.nodes}
    if len(nodes) != len(workflow.nodes):
        errors.append("duplicate node ids")
    for node in workflow.nodes:
        if node.skill not in skills:
            errors.append(f"unknown skill: {node.skill}")
        if node.capability not in capabilities:
            errors.append(f"unknown capability: {node.capability}")
        if (node.prompt.prompt_id, node.prompt.version) not in prompts:
            errors.append(f"unknown prompt: {node.prompt.prompt_id}@{node.prompt.version}")
        if (node.rubric.rubric_id, node.rubric.version) not in rubrics:
            errors.append(f"unknown rubric: {node.rubric.rubric_id}@{node.rubric.version}")
        if (
            node.agent_profile
            and (node.agent_profile.prompt_id, node.agent_profile.version) not in profiles
        ):
            errors.append(
                f"unknown profile: {node.agent_profile.prompt_id}@{node.agent_profile.version}"
            )
        try:
            resolve_agent_role(node)
        except AgentRoleRoutingError as exc:
            errors.append(str(exc))
        for dependency in node.dependencies:
            if dependency not in nodes:
                errors.append(f"dangling dependency: {node.node_id}->{dependency}")
        read_ids = {artifact.artifact_id for artifact in node.reads}
        write_ids = {artifact.artifact_id for artifact in node.writes}
        if read_ids & write_ids:
            errors.append(f"artifact read/write mismatch: {node.node_id}")
        if (
            node.completion_mode in {"conditional", "optional"}
            and not node.skip_policy.record_reason
        ):
            errors.append(f"missing skip reason handling: {node.node_id}")
        if node.task_type in {"experiment_execution", "tool_execution", "component_execution"}:
            if not node.experiment_plan_binding or not node.decision_binding:
                errors.append(f"execution bindings missing: {node.node_id}")
        if (
            workflow.extension_policy.allow_execution
            and workflow.extension_policy.allow_dynamic_tasks
        ):
            errors.append("dynamic extension policy cannot allow execution bypass")
    if _has_cycle(workflow):
        errors.append("workflow graph contains a cycle")
    if errors:
        raise WorkflowValidationError("; ".join(errors))
    return workflow


def _has_cycle(workflow: WorkflowDefinition) -> bool:
    indegree = {node.node_id: 0 for node in workflow.nodes}
    children: dict[str, list[str]] = defaultdict(list)
    for node in workflow.nodes:
        for dependency in node.dependencies:
            if dependency in indegree:
                indegree[node.node_id] += 1
                children[dependency].append(node.node_id)
    queue = deque(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return visited != len(indegree)
