"""Deterministic routing from a workflow node to a dispatchable agent role.

A node that names an agent profile is dispatched as that profile's `agent_role`;
a node that does not falls back to the skill it declares.  Both paths land
inside the roster in `services.contracts.agent_roles`, so no free-text asset
name can become an agent name.
"""

from __future__ import annotations

from collections.abc import Mapping

from services.contracts import DISPATCHABLE_AGENT_ROLES, AgentProfile, WorkflowNode

ProfileKey = tuple[str, str]

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


def resolve_agent_role(
    node: WorkflowNode,
    *,
    profiles: Mapping[ProfileKey, AgentProfile] | None = None,
) -> str:
    """Resolve one node to its agent role, failing closed when unroutable."""
    if node.agent_profile is not None:
        key = (node.agent_profile.prompt_id, node.agent_profile.version)
        profile = (profiles or {}).get(key)
        if profile is None:
            # The profile decides the role, so an unreadable one is a routing
            # failure rather than a reason to guess from the skill.
            raise AgentRoleRoutingError(
                f"node {node.node_id!r} names profile {key[0]}@{key[1]}, which was not resolved"
            )
        role = profile.agent_role
    else:
        role = SKILL_AGENT_ROLES.get(node.skill)
    if role is None:
        raise AgentRoleRoutingError(
            f"node {node.node_id!r} has no agent role for skill {node.skill!r}"
        )
    if role not in DISPATCHABLE_AGENT_ROLES:
        raise AgentRoleRoutingError(f"node {node.node_id!r} routes to undispatchable role {role!r}")
    return role


__all__ = [
    "SKILL_AGENT_ROLES",
    "AgentRoleRoutingError",
    "ProfileKey",
    "resolve_agent_role",
]
