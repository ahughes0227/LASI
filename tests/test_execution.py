from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, Field
from services.contracts import (
    Goal,
    OperatorSpec,
    Plan,
    PlanStep,
    SessionStatus,
    StepStatus,
)
from services.execution import ExecutionDenied


class PositiveInput(BaseModel):
    value: int = Field(gt=0)


def make_plan(operator: str = "echo", arguments=None) -> Plan:
    return Plan(
        plan_id=f"plan-{operator}",
        goal=Goal(goal_id=f"goal-{operator}", project_id="project-1", objective="run"),
        requester_id="requester",
        planner_profile_id="planner-profile",
        steps=(
            PlanStep(
                step_id="step-1",
                operator=operator,
                arguments=arguments or {"value": 1},
                rationale="deterministic execution",
            ),
        ),
    )


def authorize(core, plan: Plan):
    core.store.record_plan(plan)
    result = core.verifier.verify(plan)
    core.store.record_decision(result)
    assert result.allowed
    return result


def test_subprocess_execution_and_idempotent_replay(core) -> None:
    async def scenario():
        plan = make_plan()
        decision = authorize(core, plan)
        first = await core.executor.execute(plan, decision)
        second = await core.executor.execute(plan, decision)
        return first, second

    first, second = asyncio.run(scenario())
    assert first.status == SessionStatus.SUCCEEDED
    assert first.steps[0].result.outputs == {"echo": {"value": 1}}
    assert second.steps[0].reused


def test_timeout_is_structured_failure(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="slow",
            description="Sleeps.",
            version="1",
            entrypoint="services.builtin_operators:sleep",
            implementation_digest="slow-v1",
            timeout_seconds=0.05,
        )
    )
    plan = make_plan("slow", {"seconds": 1})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    assert result.status == SessionStatus.FAILED
    assert result.steps[0].result.failure_code == "timeout"


def test_non_idempotent_ambiguous_exit_requires_reconciliation(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="ambiguous",
            description="Exits without result.",
            version="1",
            entrypoint="services.builtin_operators:hard_exit",
            implementation_digest="exit-v1",
            idempotent=False,
        )
    )
    plan = make_plan("ambiguous", {"code": 9})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    assert result.status == SessionStatus.RECONCILIATION_REQUIRED
    assert result.steps[0].status == StepStatus.RECONCILIATION_REQUIRED


def test_artifact_is_content_addressed(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="artifact",
            description="Writes an artifact.",
            version="1",
            entrypoint="services.builtin_operators:write_artifact",
            implementation_digest="artifact-v1",
        )
    )
    plan = make_plan("artifact", {"content": "hello"})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    receipt = result.steps[0].result.artifacts[0]
    assert receipt.size_bytes == 5
    assert receipt.uri.startswith("file://")


def test_parent_environment_is_not_inherited_without_allowlist(core, monkeypatch) -> None:
    monkeypatch.setenv("LASI_SECRET_TEST_VALUE", "must-not-leak")
    core.registry.register(
        OperatorSpec(
            name="environment",
            description="Reports selected environment names.",
            version="1",
            entrypoint="services.builtin_operators:environment",
            implementation_digest="environment-v1",
        )
    )
    plan = make_plan("environment", {"keys": ["LASI_SECRET_TEST_VALUE", "PATH"]})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    assert result.steps[0].result.outputs == {"present": ["PATH"]}


def test_artifact_symlink_is_rejected(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="symlink-artifact",
            description="Produces a symlink for policy testing.",
            version="1",
            entrypoint="services.builtin_operators:write_symlink_artifact",
            implementation_digest="symlink-v1",
        )
    )
    plan = make_plan("symlink-artifact", {"content": "hello"})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    assert result.status == SessionStatus.FAILED
    assert result.steps[0].result.failure_code == "invalid_result"


def test_execution_rechecks_revoked_grants(core) -> None:
    plan = make_plan()
    decision = authorize(core, plan)
    core.store.revoke_execution_grant("execute-requester")
    with pytest.raises(ExecutionDenied, match="authorization"):
        asyncio.run(core.executor.execute(plan, decision))


def test_registry_derives_and_enforces_the_executable_schema(core) -> None:
    core.registry.register(
        OperatorSpec(
            name="typed-echo",
            description="Echoes a positive integer.",
            version="1",
            entrypoint="services.builtin_operators:echo",
            implementation_digest="typed-echo-v1",
        ),
        input_model=PositiveInput,
    )
    assert core.registry.get("typed-echo").spec.input_schema["properties"]["value"]
    plan = make_plan("typed-echo", {"value": -1})
    result = asyncio.run(core.executor.execute(plan, authorize(core, plan)))
    assert result.status == SessionStatus.FAILED
    assert result.steps[0].result.failure_code == "invalid_input"
