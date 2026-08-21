from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest
from services.contracts import (
    Evidence,
    Goal,
    Plan,
    PlanStep,
    TrustLevel,
    content_digest,
)
from services.identity import AuthenticationError
from services.ledger import AuthorityStore


def make_plan() -> Plan:
    return Plan(
        plan_id="plan-1",
        goal=Goal(goal_id="goal-1", project_id="project-1", objective="inspect"),
        requester_id="requester",
        planner_profile_id="planner-profile",
        steps=(PlanStep(step_id="echo-1", operator="echo", rationale="inspect"),),
    )


def test_authoritative_evidence_survives_restart(core) -> None:
    core.store.add_evidence(
        Evidence(
            evidence_id="e-1",
            project_id="project-1",
            source="human",
            content="observation",
            trust=TrustLevel.CORROBORATED,
        )
    )
    path = core.store.path
    core.store.close()
    reopened = AuthorityStore(path)
    assert reopened.evidence("project-1")[0].content == "observation"


def test_signed_action_is_payload_bound_and_replay_protected(core) -> None:
    goal = Goal(goal_id="g", project_id="p", objective="learn")
    action = core.signers["requester"].sign(action="start_goal", payload=goal)
    principal = core.identities.authenticate(
        action, expected_action="start_goal", expected_payload=goal
    )
    assert principal.subject_id == "requester"
    with pytest.raises(AuthenticationError, match="nonce"):
        core.identities.authenticate(action, expected_action="start_goal", expected_payload=goal)


def test_expired_and_tampered_actions_are_rejected(core) -> None:
    payload = {"session_id": "s"}
    expired = core.signers["requester"].sign(
        action="cancel_session", payload=payload, ttl=timedelta(seconds=-1)
    )
    with pytest.raises(AuthenticationError, match="expired"):
        core.identities.authenticate(
            expired, expected_action="cancel_session", expected_payload=payload
        )
    valid = core.signers["requester"].sign(action="cancel_session", payload=payload)
    with pytest.raises(AuthenticationError, match="digest"):
        core.identities.authenticate(
            valid,
            expected_action="cancel_session",
            expected_payload={"session_id": "different"},
        )


def test_plan_is_immutable_and_identical_decisions_are_deduplicated(core) -> None:
    plan = make_plan()
    core.store.record_plan(plan)
    first = core.verifier.verify(plan)
    second = core.verifier.verify(plan)
    core.store.record_decision(first)
    core.store.record_decision(second)
    assert first.decision_id == second.decision_id
    assert core.store.latest_decision(plan.plan_id).decision_id == second.decision_id
    changed = plan.model_copy(
        update={
            "steps": (
                PlanStep(
                    step_id="echo-1",
                    operator="echo",
                    arguments={"changed": True},
                    rationale="inspect",
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="different digest"):
        core.store.record_plan(changed)


def test_canonical_digest_is_order_independent() -> None:
    assert content_digest({"a": 1, "b": 2}) == content_digest({"b": 2, "a": 1})


def test_coordinator_lease_excludes_a_second_owner(core) -> None:
    assert core.store.acquire_lease("owner-one")
    competing = AuthorityStore(core.store.path)
    try:
        assert not competing.acquire_lease("owner-two")
        assert competing.acquire_lease("owner-one")
    finally:
        competing.close()


def test_legacy_unversioned_database_is_backed_up_and_rejected(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE old_runtime_state(value TEXT)")
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="non-empty unversioned"):
        AuthorityStore(path)

    assert path.exists()
    assert len(tuple(tmp_path.glob("legacy.v0.*.backup.sqlite3"))) == 1


def test_planner_profile_identity_is_immutable(core) -> None:
    changed = core.profile.model_copy(update={"service_identity_id": "approver-1"})
    with pytest.raises(ValueError, match="different content"):
        core.store.save_planner_profile(changed)
