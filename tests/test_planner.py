from __future__ import annotations

import asyncio

from services.contracts import Goal, MemoryContext, Plan, PlanStep
from services.planning import LangChainPlanner


class FakeRunnable:
    async def ainvoke(self, payload: dict[str, object]) -> dict[str, object]:
        goal = payload["goal"]
        assert isinstance(goal, dict)
        return {
            "plan_id": "plan-1",
            "goal": goal,
            "proposed_by": "spoofed",
            "steps": [
                {
                    "step_id": "step-1",
                    "operator": "inspect",
                    "arguments": {},
                    "rationale": "inspect first",
                }
            ],
        }


def test_langchain_adapter_normalizes_plan_and_provider_identity() -> None:
    async def scenario() -> Plan:
        planner = LangChainPlanner(FakeRunnable(), planner_id="planner-profile-1")
        return await planner.propose(
            goal=Goal(goal_id="goal-1", project_id="project-1", objective="diagnose"),
            memory=MemoryContext(project_id="project-1"),
            operators=(),
            pressure=(),
        )

    result = asyncio.run(scenario())
    assert result.proposed_by == "planner-profile-1"
    assert result.steps == (
        PlanStep(step_id="step-1", operator="inspect", rationale="inspect first"),
    )
