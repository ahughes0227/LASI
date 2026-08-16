"""Tests for the closed agent-role set, tool denial, and child environments."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from services.admin import AssignmentAdminService, open_admin_service
from services.contracts import (
    BUILDER_AGENT_ROLES,
    DISPATCHABLE_AGENT_ROLES,
    SPECIALIST_AGENT_ROLES,
    AgentProfile,
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
from services.memory import Decision, RuntimeTaskRecord, TaskGraphProposalRecord
from services.runtime import ProposalOrigin, TaskRuntimeService
from services.runtime.opencode import _agent_environment
from services.workflows import WorkflowRegistry
from services.workflows.binding import WorkflowBindings
from services.workflows.roles import (
    SKILL_AGENT_ROLES,
    AgentRoleRoutingError,
    resolve_agent_role,
)

ROOT = Path(__file__).resolve().parents[1]


def _revision(admin, assignment_id: str) -> int:
    """The graph revision a planner would have observed for its next proposal."""
    return admin.status(assignment_id).assignment.graph_revision


def _installed_profiles() -> dict[tuple[str, str], AgentProfile]:
    bindings = WorkflowBindings(ROOT / "system")
    return {
        (path.parent.name, path.stem): bindings.profile(path.parent.name, path.stem)
        for path in (ROOT / "system" / "agent_profiles").glob("*/*.json")
    }


def _task_spec(
    agent_role: str,
    *,
    project_id: str = "project",
    task_id: str = "task-1",
    rubric_id: str = "result-analysis",
    decision_id: str | None = None,
) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        project_id=project_id,
        task_type="result_analysis",
        agent_role=agent_role,
        description="Interpret the current evidence.",
        rubric_id=rubric_id,
        rubric_version="1.0",
        decision_id=decision_id,
    )


def _assignment(tmp_path: Path) -> tuple[AssignmentAdminService, str, TaskRuntimeService]:
    admin = open_admin_service(
        database_url=f"sqlite:///{tmp_path / 'operational.sqlite3'}", workspace=tmp_path
    )
    assignment_id = admin.start(
        project_id="dispatch-project",
        objective="exercise the dispatch gates",
        loop_policy=ResearchLoopPolicy(objective_metric="rmsle", objective_direction="minimize"),
        launch_worker=False,
    ).assignment.assignment_id
    return admin, assignment_id, TaskRuntimeService(admin.memory)


def _builder_proposal(
    admin: AssignmentAdminService,
    assignment_id: str,
    *,
    proposal_id: str,
    decision_id: str | None = None,
) -> TaskGraphProposal:
    return TaskGraphProposal(
        proposal_id=proposal_id,
        assignment_id=assignment_id,
        project_id="dispatch-project",
        observed_revision=_revision(admin, assignment_id),
        rationale="Build a component to progress the objective.",
        tasks=[
            _task_spec(
                "lasi-component-builder",
                project_id="dispatch-project",
                task_id=f"{proposal_id}-build",
                rubric_id="scientific-exploration",
                decision_id=decision_id,
            )
        ],
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
    admin, assignment_id, runtime = _assignment(tmp_path)
    proposal = TaskGraphProposal(
        proposal_id="proposal-smuggled",
        assignment_id=assignment_id,
        project_id="dispatch-project",
        observed_revision=_revision(admin, assignment_id),
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


def test_an_agent_authored_graph_cannot_reach_a_builder_role(tmp_path: Path) -> None:
    admin, assignment_id, runtime = _assignment(tmp_path)

    ingestion = runtime.ingest_proposal(
        _builder_proposal(admin, assignment_id, proposal_id="proposal-unauthorized-build"),
        origin=ProposalOrigin.AGENT,
    )

    assert not ingestion.accepted
    assert ingestion.rejection_reason is not None
    assert "requires an allowing decision" in ingestion.rejection_reason
    assert admin.memory.get(RuntimeTaskRecord, "proposal-unauthorized-build-build") is None


def test_an_allowing_decision_admits_a_builder_role(tmp_path: Path) -> None:
    admin, assignment_id, runtime = _assignment(tmp_path)
    admin.memory.add(
        Decision(
            decision_id="decision-allow-build",
            project_id="dispatch-project",
            decision="allow",
            allowed=True,
            payload={},
        )
    )

    ingestion = runtime.ingest_proposal(
        _builder_proposal(
            admin,
            assignment_id,
            proposal_id="proposal-authorized-build",
            decision_id="decision-allow-build",
        ),
        origin=ProposalOrigin.AGENT,
    )

    assert ingestion.accepted
    task = admin.memory.get(RuntimeTaskRecord, "proposal-authorized-build-build")
    assert task is not None and task.agent_role == "lasi-component-builder"


def test_a_blocking_decision_does_not_admit_a_builder_role(tmp_path: Path) -> None:
    admin, assignment_id, runtime = _assignment(tmp_path)
    admin.memory.add(
        Decision(
            decision_id="decision-block-build",
            project_id="dispatch-project",
            decision="block",
            allowed=False,
            payload={},
        )
    )

    ingestion = runtime.ingest_proposal(
        _builder_proposal(
            admin,
            assignment_id,
            proposal_id="proposal-blocked-build",
            decision_id="decision-block-build",
        ),
        origin=ProposalOrigin.AGENT,
    )

    assert not ingestion.accepted
    assert "requires an allowing decision" in (ingestion.rejection_reason or "")


def test_a_compiled_workflow_may_name_a_builder_role(tmp_path: Path) -> None:
    admin, assignment_id, runtime = _assignment(tmp_path)

    ingestion = runtime.ingest_proposal(
        _builder_proposal(admin, assignment_id, proposal_id="proposal-compiled-build"),
        origin=ProposalOrigin.WORKFLOW,
    )

    assert ingestion.accepted
    task = admin.memory.get(RuntimeTaskRecord, "proposal-compiled-build-build")
    assert task is not None and task.agent_role == "lasi-component-builder"


def test_ingestion_records_where_each_graph_came_from(tmp_path: Path) -> None:
    admin, assignment_id, runtime = _assignment(tmp_path)
    runtime.ingest_proposal(
        _builder_proposal(admin, assignment_id, proposal_id="proposal-origin-agent"),
        origin=ProposalOrigin.AGENT,
    )
    runtime.ingest_proposal(
        _builder_proposal(admin, assignment_id, proposal_id="proposal-origin-workflow"),
        origin=ProposalOrigin.WORKFLOW,
    )

    records = {
        proposal_id: admin.memory.get(TaskGraphProposalRecord, proposal_id)
        for proposal_id in ("proposal-origin-agent", "proposal-origin-workflow")
    }

    assert records["proposal-origin-agent"].origin == "agent"
    assert records["proposal-origin-agent"].status == "rejected"
    assert records["proposal-origin-workflow"].origin == "workflow"
    assert records["proposal-origin-workflow"].status == "accepted"
    # The assignment bootstrap is first-party, and says so.
    bootstrap = admin.memory.get(TaskGraphProposalRecord, f"proposal-{assignment_id}-bootstrap")
    assert bootstrap is not None and bootstrap.origin == "runtime"


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

    environment = _agent_environment("lasi-coordinator")
    inline = json.loads(environment["OPENCODE_CONFIG_CONTENT"])

    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["LASI_INTERNAL_TASK_AGENT"] == "1"
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
    profiles = _installed_profiles()

    for workflow in registry.install_all():
        for node in workflow.nodes:
            assert resolve_agent_role(node, profiles=profiles) in DISPATCHABLE_AGENT_ROLES


def test_a_named_profile_decides_the_role_over_the_skill() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("experiment_research_loop")
    node = next(item for item in workflow.nodes if item.node_id == "critique_and_falsify")

    # The node's `scientist-review` skill alone would route it to the reviewer.
    assert SKILL_AGENT_ROLES[node.skill] == "scientist-reviewer"
    assert resolve_agent_role(node, profiles=_installed_profiles()) == "scientific-critic"


def test_a_profile_naming_an_undispatchable_role_fails_to_load() -> None:
    with pytest.raises(ValidationError, match="unknown agent_role"):
        AgentProfile(profile_id="shell_worker", version="1.0", agent_role="worker")


def test_routing_fails_closed_when_a_named_profile_is_unresolved() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("experiment_research_loop")
    node = next(item for item in workflow.nodes if item.node_id == "critique_and_falsify")

    with pytest.raises(AgentRoleRoutingError, match="was not resolved"):
        resolve_agent_role(node, profiles={})


def test_workflow_routing_fails_closed_for_an_unmapped_skill() -> None:
    registry = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflow = registry.install("ticket_intake")
    node = workflow.nodes[0].model_copy(update={"skill": "shell-access"})

    with pytest.raises(AgentRoleRoutingError, match="no agent role"):
        resolve_agent_role(node)
