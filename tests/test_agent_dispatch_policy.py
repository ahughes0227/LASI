"""Tests for the closed agent-role set, tool denial, and child environments."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from services.admin import open_admin_service
from services.admin.runner import _internal_coordinator_environment
from services.contracts import (
    BUILDER_AGENT_ROLES,
    DISPATCHABLE_AGENT_ROLES,
    SPECIALIST_AGENT_ROLES,
    ResearchLoopPolicy,
    TaskGraphProposal,
    TaskSpec,
    UnknownAgentRoleError,
    validate_agent_role,
)
from services.core import (
    AGENT_ENVIRONMENT_ALLOWLIST,
    COMPONENT_ENVIRONMENT_ALLOWLIST,
    build_child_environment,
)
from services.memory import RuntimeTaskRecord
from services.runtime import TaskRuntimeService
from services.runtime.opencode import _agent_environment
from services.workflows import WorkflowRegistry
from services.workflows.roles import AgentRoleRoutingError, resolve_agent_role

ROOT = Path(__file__).resolve().parents[1]


def _task_spec(agent_role: str, *, project_id: str = "project") -> TaskSpec:
    return TaskSpec(
        task_id="task-1",
        project_id=project_id,
        task_type="result_analysis",
        agent_role=agent_role,
        description="Interpret the current evidence.",
        rubric_id="result-analysis",
        rubric_version="1.0",
    )


def test_dispatchable_roles_exclude_the_human_control_surface() -> None:
    assert "lasi-admin" not in DISPATCHABLE_AGENT_ROLES
    assert SPECIALIST_AGENT_ROLES.isdisjoint(BUILDER_AGENT_ROLES)


def test_every_dispatchable_role_has_a_checked_in_agent_definition() -> None:
    defined = {path.stem for path in (ROOT / ".opencode" / "agent").glob("*.md")}
    assert DISPATCHABLE_AGENT_ROLES <= defined


def test_task_spec_rejects_an_agent_role_outside_the_frozen_set() -> None:
    with pytest.raises(ValidationError, match="unknown agent_role"):
        _task_spec("evaluation")
    with pytest.raises(UnknownAgentRoleError):
        validate_agent_role("lasi-admin")
    assert _task_spec("scientist-reviewer").agent_role == "scientist-reviewer"


def test_proposal_parsing_rejects_an_invented_role_before_ingestion() -> None:
    payload = {
        "proposal_id": "proposal-1",
        "assignment_id": "assignment-1",
        "project_id": "project",
        "observed_revision": 1,
        "rationale": "Escalate privileges through an invented agent name.",
        "tasks": [_task_spec("scientist-reviewer").model_dump(mode="json")],
    }
    payload["tasks"][0]["agent_role"] = "lasi-capability-builder-2"

    with pytest.raises(ValidationError, match="unknown agent_role"):
        TaskGraphProposal.model_validate(payload)


def test_runtime_ingestion_rejects_a_role_that_bypassed_the_contract(tmp_path: Path) -> None:
    admin = open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )
    assignment_id = admin.start(
        project_id="dispatch-project",
        objective="prove the runtime rejects undispatchable roles",
        loop_policy=ResearchLoopPolicy(objective_metric="rmsle", objective_direction="minimize"),
        launch_worker=False,
    ).assignment.assignment_id
    runtime = TaskRuntimeService(admin.memory)
    proposal = TaskGraphProposal(
        proposal_id="proposal-smuggled",
        assignment_id=assignment_id,
        project_id="dispatch-project",
        observed_revision=1,
        rationale="Route work to an agent the roster does not contain.",
        tasks=[_task_spec("scientist-reviewer", project_id="dispatch-project")],
    )
    # Copies stand in for a payload that reached the runtime without crossing
    # the contract boundary, so the runtime guard is exercised on its own.
    smuggled = proposal.model_copy(
        update={"tasks": [proposal.tasks[0].model_copy(update={"agent_role": "shell-runner"})]}
    )

    ingestion = runtime.ingest_proposal(smuggled)

    assert not ingestion.accepted
    assert ingestion.rejection_reason is not None
    assert "undispatchable agent role" in ingestion.rejection_reason
    assert admin.memory.get(RuntimeTaskRecord, "task-1") is None


def test_specialist_dispatch_denies_edit_and_bash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"share":"disabled"}')

    inline = json.loads(_agent_environment("scientist-reviewer")["OPENCODE_CONFIG_CONTENT"])

    assert inline["default_agent"] == "scientist-reviewer"
    assert inline["agent"]["scientist-reviewer"]["mode"] == "primary"
    assert inline["agent"]["scientist-reviewer"]["permission"] == {"edit": "deny", "bash": "deny"}
    assert inline["share"] == "disabled"


def test_specialist_dispatch_overrides_an_inherited_permission_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OPENCODE_CONFIG_CONTENT",
        '{"agent":{"scientific-critic":{"permission":{"edit":"allow","bash":"allow"}}}}',
    )

    inline = json.loads(_agent_environment("scientific-critic")["OPENCODE_CONFIG_CONTENT"])

    assert inline["agent"]["scientific-critic"]["permission"] == {"edit": "deny", "bash": "deny"}


def test_builder_dispatch_keeps_its_configured_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)

    inline = json.loads(_agent_environment("lasi-component-builder")["OPENCODE_CONFIG_CONTENT"])

    assert "permission" not in inline["agent"]["lasi-component-builder"]


def test_dispatch_refuses_a_role_outside_the_frozen_set() -> None:
    with pytest.raises(UnknownAgentRoleError):
        _agent_environment("lasi-admin")


def test_agent_environment_is_built_from_the_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "operator-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "operator-token")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
    monkeypatch.delenv("LASI_CHILD_ENV_PASSTHROUGH", raising=False)

    environment = _agent_environment("scientist-reviewer")

    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert environment["PATH"] == "/usr/bin"
    assert environment["LASI_INTERNAL_TASK_AGENT"] == "1"


def test_coordinator_environment_is_allowlisted_and_stays_planning_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "operator-secret")
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"share":"disabled"}')
    monkeypatch.delenv("LASI_CHILD_ENV_PASSTHROUGH", raising=False)

    environment = _internal_coordinator_environment()
    inline = json.loads(environment["OPENCODE_CONFIG_CONTENT"])

    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["LASI_INTERNAL_COORDINATOR"] == "1"
    assert inline["agent"]["lasi-coordinator"]["permission"] == {"edit": "deny", "bash": "deny"}


def test_operator_passthrough_extends_the_allowlist_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.internal:3128")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "operator-secret")
    monkeypatch.setenv("LASI_CHILD_ENV_PASSTHROUGH", "HTTPS_PROXY")

    environment = build_child_environment(AGENT_ENVIRONMENT_ALLOWLIST)

    assert environment["HTTPS_PROXY"] == "http://proxy.internal:3128"
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "LASI_CHILD_ENV_PASSTHROUGH" not in environment


def test_component_environment_withholds_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-key")
    monkeypatch.delenv("LASI_CHILD_ENV_PASSTHROUGH", raising=False)

    environment = build_child_environment(COMPONENT_ENVIRONMENT_ALLOWLIST)

    assert "ANTHROPIC_API_KEY" not in environment
    assert "PATH" in environment


def test_every_installed_workflow_node_routes_to_a_dispatchable_role() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")

    for workflow in registry.install_all():
        for node in workflow.nodes:
            assert resolve_agent_role(node) in DISPATCHABLE_AGENT_ROLES


def test_workflow_routing_fails_closed_for_an_unmapped_skill() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("ticket_intake")
    node = workflow.nodes[0].model_copy(update={"skill": "shell-access"})

    with pytest.raises(AgentRoleRoutingError, match="no agent role"):
        resolve_agent_role(node)
