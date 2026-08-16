"""Frozen vocabulary of agent roles the task runtime is allowed to dispatch.

An `agent_role` is not a label: it selects the OpenCode agent that a leased task
is launched as, and an unknown role would be materialised as a brand new inline
agent with whatever permissions the runtime happens to hand it.  The set is
therefore closed, and membership is checked where a role first enters the
system rather than where it is finally used.
"""

from __future__ import annotations

# Bounded specialists.  These roles are denied file edits and shell access; they
# read context, reason, and return typed artifacts and evidence references.
SPECIALIST_AGENT_ROLES: frozenset[str] = frozenset(
    {
        "component-reviewer",
        "contract-architect",
        "dataset-engineer",
        "experiment-engineer",
        "governance-reviewer",
        "knowledge-curator",
        "lasi-code-reviewer",
        "lasi-coordinator",
        "remote-execution-engineer",
        "report-outcome-engineer",
        "scientific-critic",
        "scientist-reviewer",
    }
)

# Governed package builders are the only dispatchable roles that legitimately
# write files and run commands, and only inside their own build pipelines.
BUILDER_AGENT_ROLES: frozenset[str] = frozenset(
    {
        "lasi-capability-builder",
        "lasi-component-builder",
        "lasi-workflow-builder",
    }
)

# `lasi-admin` is deliberately absent: it is the human-facing control surface and
# must never be reachable from a task graph.
DISPATCHABLE_AGENT_ROLES: frozenset[str] = SPECIALIST_AGENT_ROLES | BUILDER_AGENT_ROLES


class UnknownAgentRoleError(ValueError):
    """A role outside the frozen set was proposed for dispatch."""

    def __init__(self, agent_role: str) -> None:
        super().__init__(
            f"unknown agent_role {agent_role!r}; "
            f"allowed roles: {', '.join(sorted(DISPATCHABLE_AGENT_ROLES))}"
        )
        self.agent_role = agent_role


def validate_agent_role(agent_role: str) -> str:
    """Return the role when it is dispatchable, otherwise fail closed."""
    if agent_role not in DISPATCHABLE_AGENT_ROLES:
        raise UnknownAgentRoleError(agent_role)
    return agent_role


__all__ = [
    "BUILDER_AGENT_ROLES",
    "DISPATCHABLE_AGENT_ROLES",
    "SPECIALIST_AGENT_ROLES",
    "UnknownAgentRoleError",
    "validate_agent_role",
]
