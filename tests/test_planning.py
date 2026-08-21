from __future__ import annotations

import asyncio
import json
import stat

import pytest
from services.contracts import Goal, MemoryContext
from services.planning import (
    LiteLLMPlanner,
    PlannerError,
    PrivateInvocationStore,
    TransientModelError,
)


class RepairGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, profile, messages):
        self.calls += 1
        if self.calls == 1:
            return {"content": "not-json"}
        return {
            "content": json.dumps(
                {
                    "plan_id": "plan-model",
                    "goal": {
                        "goal_id": "goal-model",
                        "project_id": "project-1",
                        "objective": "inspect",
                    },
                    "requester_id": "spoofed",
                    "planner_profile_id": "spoofed",
                    "steps": [
                        {
                            "step_id": "echo-1",
                            "operator": "echo",
                            "rationale": "inspect",
                        }
                    ],
                }
            ),
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }


def test_litellm_planner_repairs_and_normalizes_identity(core) -> None:
    async def scenario():
        private = PrivateInvocationStore(core.root / "private-invocations")
        gateway = RepairGateway()
        planner = LiteLLMPlanner(
            profile=core.profile,
            gateway=gateway,
            store=core.store,
            private_store=private,
        )
        plan = await planner.propose(
            session_id="session-1",
            requester_id="requester",
            goal=Goal(goal_id="goal-model", project_id="project-1", objective="inspect"),
            memory=MemoryContext(project_id="project-1"),
            operators=core.registry.specs(),
            pressure=(),
        )
        return plan, gateway, private

    plan, gateway, private = asyncio.run(scenario())
    assert gateway.calls == 2
    assert plan.requester_id == "requester"
    assert plan.planner_profile_id == core.profile.profile_id
    assert stat.S_IMODE(next(private.root.iterdir()).stat().st_mode) == 0o600


class TransientGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, profile, messages):
        self.calls += 1
        raise TransientModelError("later")


def test_transient_failure_is_bounded(core) -> None:
    gateway = TransientGateway()
    planner = LiteLLMPlanner(
        profile=core.profile.model_copy(
            update={"profile_id": "bounded-retry-profile", "max_transient_attempts": 2}
        ),
        gateway=gateway,
        store=core.store,
        private_store=PrivateInvocationStore(core.root / "private-failures"),
    )
    with pytest.raises(PlannerError, match="later"):
        asyncio.run(
            planner.propose(
                session_id="session-fail",
                requester_id="requester",
                goal=Goal(goal_id="g", project_id="p", objective="x"),
                memory=MemoryContext(project_id="p"),
                operators=(),
                pressure=(),
            )
        )
    assert gateway.calls == 2
