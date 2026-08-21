from __future__ import annotations

import asyncio

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from services.contracts import Goal, OperatorSpec, Plan, PlanStep, SessionStatus
from services.identity import LocalSigner
from services.memory import InMemoryProjection, MemoryService
from services.orchestration import LasiGraph, LasiRuntime
from services.policy import ExplorationPolicy


class FixedPlanner:
    def __init__(self, profile_id: str, operator: str = "echo") -> None:
        self.profile_id = profile_id
        self.operator = operator
        self.calls = 0

    async def propose(
        self,
        *,
        requester_id: str,
        goal: Goal,
        **_: object,
    ) -> Plan:
        self.calls += 1
        return Plan(
            plan_id=f"plan-{goal.goal_id}",
            goal=goal,
            requester_id=requester_id,
            planner_profile_id=self.profile_id,
            steps=(
                PlanStep(
                    step_id="step-1",
                    operator=self.operator,
                    arguments={"value": 1},
                    rationale="fixed test plan",
                ),
            ),
        )


def test_durable_langgraph_runs_signed_goal(core) -> None:
    async def scenario():
        planner = FixedPlanner(core.profile.profile_id)
        async with AsyncSqliteSaver.from_conn_string(
            str(core.root / "checkpoints.sqlite3")
        ) as saver:
            graph = LasiGraph(
                memory=MemoryService(core.store, InMemoryProjection()),
                planner=planner,
                registry=core.registry,
                verifier=core.verifier,
                executor=core.executor,
                exploration=ExplorationPolicy(),
                store=core.store,
            ).build(checkpointer=saver)
            runtime = LasiRuntime(
                graph=graph,
                store=core.store,
                identities=core.identities,
                approvals=core.approvals,
            )
            goal = Goal(goal_id="runtime", project_id="project-1", objective="inspect")
            state = await runtime.start(
                goal,
                core.signers["requester"].sign(action="start_goal", payload=goal),
            )
            return state, planner

    state, planner = asyncio.run(scenario())
    assert state["status"] == SessionStatus.SUCCEEDED
    assert planner.calls == 1


def test_approval_interrupt_resumes_from_sqlite_checkpoint(core) -> None:
    async def scenario():
        core.registry.register(
            OperatorSpec(
                name="high-runtime",
                description="High risk runtime action.",
                version="1",
                entrypoint="services.builtin_operators:echo",
                implementation_digest="high-runtime-v1",
                risk="high",
            )
        )
        planner = FixedPlanner(core.profile.profile_id, "high-runtime")
        async with AsyncSqliteSaver.from_conn_string(
            str(core.root / "approval-checkpoints.sqlite3")
        ) as saver:
            graph = LasiGraph(
                memory=MemoryService(core.store, InMemoryProjection()),
                planner=planner,
                registry=core.registry,
                verifier=core.verifier,
                executor=core.executor,
                exploration=ExplorationPolicy(),
                store=core.store,
            ).build(checkpointer=saver)
            runtime = LasiRuntime(
                graph=graph,
                store=core.store,
                identities=core.identities,
                approvals=core.approvals,
            )
            goal = Goal(goal_id="approval", project_id="project-1", objective="change")
            waiting = await runtime.start(
                goal,
                core.signers["requester"].sign(action="start_goal", payload=goal),
            )
            request_id = waiting["approval_request_ids"][0]
            reason = "reviewed"
            payload = {"request_id": request_id, "choice": "approve", "reason": reason}
            runtime.decide_approval(
                request_id=request_id,
                choice="approve",
                reason=reason,
                signed_action=core.signers["approver-1"].sign(
                    action="approval_decision", payload=payload
                ),
            )
            resume_payload = {"session_id": waiting["session_id"]}
            completed = await runtime.resume(
                waiting["session_id"],
                core.signers["requester"].sign(action="resume_session", payload=resume_payload),
            )
            return waiting, completed, planner

    waiting, completed, planner = asyncio.run(scenario())
    assert waiting["status"] == SessionStatus.AWAITING_APPROVAL
    assert completed["status"] == SessionStatus.SUCCEEDED
    assert planner.calls == 1


def test_only_requester_or_admin_can_resume(core) -> None:
    async def scenario():
        observer = LocalSigner.generate("observer")
        core.store.register_identity(observer.identity_record())
        core.registry.register(
            OperatorSpec(
                name="guarded-runtime",
                description="High risk runtime action.",
                version="1",
                entrypoint="services.builtin_operators:echo",
                implementation_digest="guarded-runtime-v1",
                risk="high",
            )
        )
        planner = FixedPlanner(core.profile.profile_id, "guarded-runtime")
        async with AsyncSqliteSaver.from_conn_string(
            str(core.root / "authorization-checkpoints.sqlite3")
        ) as saver:
            graph = LasiGraph(
                memory=MemoryService(core.store, InMemoryProjection()),
                planner=planner,
                registry=core.registry,
                verifier=core.verifier,
                executor=core.executor,
                exploration=ExplorationPolicy(),
                store=core.store,
            ).build(checkpointer=saver)
            runtime = LasiRuntime(
                graph=graph,
                store=core.store,
                identities=core.identities,
                approvals=core.approvals,
            )
            goal = Goal(goal_id="guarded", project_id="project-1", objective="change")
            waiting = await runtime.start(
                goal,
                core.signers["requester"].sign(action="start_goal", payload=goal),
            )
            payload = {"session_id": waiting["session_id"]}
            with pytest.raises(PermissionError, match="requester"):
                await runtime.resume(
                    waiting["session_id"],
                    observer.sign(action="resume_session", payload=payload),
                )

    asyncio.run(scenario())
