"""Deterministic routing from a workflow node to a dispatchable agent role.

Workflow nodes declare a skill and a capability, not an agent.  Routing them
through a frozen table keeps the compiler from turning a free-text asset name
into an agent name, and keeps every emitted `TaskSpec` inside the roster in
`services.contracts.agent_roles`.
"""

from __future__ import annotations

from services.contracts import DISPATCHABLE_AGENT_ROLES, WorkflowNode

# Agent profiles that name a specific specialist.  A generic profile (for
# example `default_worker`) is intentionally absent: it defers to the skill.
PROFILE_AGENT_ROLES: dict[str, str] = {
    "scientific_critic": "scientific-critic",
}

SKILL_AGENT_ROLES: dict[str, str] = {
    "capability-development": "lasi-capability-builder",
    "challenge-intake": "dataset-engineer",
    "component-development": "lasi-component-builder",
    "component-review": "component-reviewer",
    "dataset-characterization": "dataset-engineer",
    "dataset-intake": "dataset-engineer",
    "decision-review": "governance-reviewer",
    "experiment-planning": "experiment-engineer",
    "knowledge-curation": "knowledge-curator",
    "outcome-recording": "report-outcome-engineer",
    "remote-execution": "remote-execution-engineer",
    "report-generation": "report-outcome-engineer",
    "scientist-review": "scientist-reviewer",
    "workflow-authoring": "lasi-workflow-builder",
    "workflow-development": "lasi-workflow-builder",
}


class AgentRoleRoutingError(ValueError):
    """A workflow node cannot be routed to a dispatchable agent role."""


def resolve_agent_role(node: WorkflowNode) -> str:
    """Resolve one node to its agent role, failing closed when unroutable."""
    profile_id = node.agent_profile.prompt_id if node.agent_profile else None
    role = PROFILE_AGENT_ROLES.get(profile_id) if profile_id else None
    role = role or SKILL_AGENT_ROLES.get(node.skill)
    if role is None:
        raise AgentRoleRoutingError(
            f"node {node.node_id!r} has no agent role for skill {node.skill!r}"
        )
    if role not in DISPATCHABLE_AGENT_ROLES:
        raise AgentRoleRoutingError(f"node {node.node_id!r} routes to undispatchable role {role!r}")
    return role


__all__ = [
    "PROFILE_AGENT_ROLES",
    "SKILL_AGENT_ROLES",
    "AgentRoleRoutingError",
    "resolve_agent_role",
]
