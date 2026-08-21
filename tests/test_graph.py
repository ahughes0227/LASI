from __future__ import annotations

import asyncio

from services.contracts import (
    Goal,
    IdentityGrant,
    OperatorResult,
    OperatorSpec,
    Plan,
    PlanStep,
)
from services.execution import DeterministicExecutor
from services.identity import IdentityGraph
from services.ledger import SqliteLedger
from services.memory import InMemoryProjection, MemoryService
from services.operators import OperatorRegistry
from services.orchestration import LasiGraph
from services.policy import ExplorationPolicy, PlanVerifier


class FixedPlanner:
    async def propose(self, *, goal: Goal, **_: object) -> Plan:
        return Plan(
            plan_id="graph-plan",
            goal=goal,
            proposed_by="fixed",
            steps=(
                PlanStep(
                    step_id="inspect-1",
                    operator="inspect",
                    rationale="collect deterministic evidence",
                ),
            ),
        )


def test_real_langgraph_runs_constitutional_loop() -> None:
    async def scenario() -> dict[str, object]:
        ledger = SqliteLedger()
        registry = OperatorRegistry()
        registry.register(
            OperatorSpec(name="inspect", description="Inspect.", version="1"),
            lambda _: OperatorResult(status="succeeded", outputs={"observed": True}),
        )
        identity = IdentityGraph(policy_version="test-v1")
        identity.add_grant(
            IdentityGrant(
                subject_id="fixed",
                operators=frozenset({"inspect"}),
            )
        )
        graph = LasiGraph(
            memory=MemoryService(ledger, InMemoryProjection()),
            identity=identity,
            planner=FixedPlanner(),
            registry=registry,
            verifier=PlanVerifier(registry, approval_checker=ledger.has_approval),
            executor=DeterministicExecutor(registry, ledger),
            exploration=ExplorationPolicy(),
        ).build()
        return await graph.ainvoke(
            {
                "goal": Goal(
                    goal_id="graph-goal",
                    project_id="graph-project",
                    objective="inspect evidence",
                ),
                "actor_id": "fixed",
            }
        )

    state = asyncio.run(scenario())
    assert state["status"] == "succeeded"
    assert state["execution"].steps[0].result.outputs == {"observed": True}
