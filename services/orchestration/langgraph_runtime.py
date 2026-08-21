"""The single constitutional loop expressed as a LangGraph state machine."""

from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import (
    ExecutionResult,
    ExplorationDirective,
    Goal,
    IdentitySnapshot,
    MemoryContext,
    Plan,
    VerificationResult,
)
from ..execution import DeterministicExecutor
from ..identity import IdentityGraph
from ..memory import MemoryService
from ..operators import OperatorRegistry
from ..planning import Planner
from ..policy import ExplorationPolicy, PlanVerifier


class LasiState(TypedDict, total=False):
    goal: Goal
    actor_id: str
    identity: IdentitySnapshot
    memory: MemoryContext
    pressure: tuple[ExplorationDirective, ...]
    plan: Plan
    verification: VerificationResult
    execution: ExecutionResult
    status: str


class LasiGraph:
    def __init__(
        self,
        *,
        memory: MemoryService,
        identity: IdentityGraph,
        planner: Planner,
        registry: OperatorRegistry,
        verifier: PlanVerifier,
        executor: DeterministicExecutor,
        exploration: ExplorationPolicy,
    ) -> None:
        self.memory = memory
        self.identity = identity
        self.planner = planner
        self.registry = registry
        self.verifier = verifier
        self.executor = executor
        self.exploration = exploration

    def build(self, *, checkpointer: Any = None) -> Any:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import interrupt

        async def retrieve(state: LasiState) -> dict[str, Any]:
            goal = state["goal"]
            context = await self.memory.context(
                project_id=goal.project_id,
                query=goal.objective,
                constraints=goal.constraints,
            )
            return {
                "memory": context,
                "identity": self.identity.snapshot(state["actor_id"]),
            }

        def pressure(state: LasiState) -> dict[str, Any]:
            return {"pressure": self.exploration.directives(state["memory"], self.registry)}

        async def plan(state: LasiState) -> dict[str, Any]:
            proposal = await self.planner.propose(
                goal=state["goal"],
                memory=state["memory"],
                operators=self.registry.specs(),
                pressure=state["pressure"],
            )
            self.executor.ledger.record_plan(proposal)
            return {"plan": proposal}

        def verify(state: LasiState) -> dict[str, Any]:
            result = self.verifier.verify(
                state["plan"],
                identity=state["identity"],
                memory=state["memory"],
            )
            self.executor.ledger.record_decision(result)
            return {"verification": result}

        def route(state: LasiState) -> str:
            verification = state["verification"]
            if verification.allowed:
                return "execute"
            return "approval" if verification.requires_approval else "denied"

        def approval(state: LasiState) -> dict[str, Any]:
            interrupt(
                {
                    "plan": state["plan"].model_dump(mode="json"),
                    "findings": [
                        item.model_dump(mode="json")
                        for item in state["verification"].findings
                    ],
                }
            )
            return {"status": "approval_resumed"}

        def execute(state: LasiState) -> dict[str, Any]:
            result = self.executor.execute(state["plan"], state["verification"])
            return {"execution": result, "status": result.status}

        async def learn(state: LasiState) -> dict[str, Any]:
            await self.memory.project_new_events(state["goal"].project_id)
            return {"status": state.get("status", "completed")}

        graph = StateGraph(LasiState)
        graph.add_node("retrieve", retrieve)
        graph.add_node("pressure", pressure)
        graph.add_node("plan", plan)
        graph.add_node("verify", verify)
        graph.add_node("approval", approval)
        graph.add_node("execute", execute)
        graph.add_node("learn", learn)
        graph.add_node("denied", lambda _: {"status": "denied"})
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "pressure")
        graph.add_edge("pressure", "plan")
        graph.add_edge("plan", "verify")
        graph.add_conditional_edges(
            "verify",
            route,
            {"execute": "execute", "approval": "approval", "denied": "denied"},
        )
        graph.add_edge("approval", "verify")
        graph.add_edge("execute", "learn")
        graph.add_edge("learn", END)
        graph.add_edge("denied", END)
        return graph.compile(checkpointer=checkpointer)
