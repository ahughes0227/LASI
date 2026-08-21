"""Durable LangGraph constitutional loop and authenticated runtime facade."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from ..contracts import (
    ApprovalChoice,
    ExecutionResult,
    ExplorationDirective,
    Goal,
    MemoryContext,
    Plan,
    SessionStatus,
    SignedAction,
    VerificationResult,
)
from ..execution import DeterministicExecutor
from ..identity import ApprovalService, IdentityService
from ..ledger import AuthorityStore
from ..memory import MemoryService
from ..operators import OperatorRegistry
from ..planning import Planner
from ..policy import ExplorationPolicy, PlanVerifier


class LasiState(TypedDict, total=False):
    session_id: str
    requester_id: str
    goal: Goal
    memory: MemoryContext
    pressure: tuple[ExplorationDirective, ...]
    plan: Plan
    verification: VerificationResult
    approval_request_ids: tuple[str, ...]
    execution: ExecutionResult
    status: SessionStatus


class LasiGraph:
    def __init__(
        self,
        *,
        memory: MemoryService,
        planner: Planner,
        registry: OperatorRegistry,
        verifier: PlanVerifier,
        executor: DeterministicExecutor,
        exploration: ExplorationPolicy,
        store: AuthorityStore,
    ) -> None:
        self.memory = memory
        self.planner = planner
        self.registry = registry
        self.verifier = verifier
        self.executor = executor
        self.exploration = exploration
        self.store = store

    def build(self, *, checkpointer: Any) -> Any:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import interrupt

        async def retrieve(state: LasiState) -> dict[str, Any]:
            goal = state["goal"]
            context = await self.memory.context(
                project_id=goal.project_id,
                query=goal.objective,
                constraints=goal.constraints,
            )
            return {"memory": context}

        def pressure(state: LasiState) -> dict[str, Any]:
            return {"pressure": self.exploration.directives(state["memory"], self.registry)}

        async def plan(state: LasiState) -> dict[str, Any]:
            existing = state.get("plan")
            if existing is not None:
                return {"plan": existing}
            proposal = await self.planner.propose(
                session_id=state["session_id"],
                requester_id=state["requester_id"],
                goal=state["goal"],
                memory=state["memory"],
                operators=self.registry.specs(),
                pressure=state["pressure"],
            )
            self.store.record_plan(proposal)
            return {"plan": proposal}

        def verify(state: LasiState) -> dict[str, Any]:
            result = self.verifier.verify(state["plan"])
            self.store.record_decision(result)
            return {"verification": result}

        def route(state: LasiState) -> str:
            verification = state["verification"]
            if verification.allowed:
                return "execute"
            return "request_approval" if verification.requires_approval else "denied"

        def request_approval(state: LasiState) -> dict[str, Any]:
            request_ids = self.verifier.ensure_approval_requests(state["plan"])
            self.store.update_session(state["session_id"], SessionStatus.AWAITING_APPROVAL)
            return {
                "approval_request_ids": request_ids,
                "status": SessionStatus.AWAITING_APPROVAL,
            }

        def approval(state: LasiState) -> dict[str, Any]:
            interrupt(
                {
                    "session_id": state["session_id"],
                    "plan_id": state["plan"].plan_id,
                    "request_ids": list(state["approval_request_ids"]),
                    "findings": [
                        item.model_dump(mode="json") for item in state["verification"].findings
                    ],
                }
            )
            return {}

        async def execute(state: LasiState) -> dict[str, Any]:
            self.store.update_session(state["session_id"], SessionStatus.RUNNING)
            result = await self.executor.execute(state["plan"], state["verification"])
            self.store.update_session(state["session_id"], result.status)
            return {"execution": result, "status": result.status}

        def denied(state: LasiState) -> dict[str, Any]:
            self.store.update_session(state["session_id"], SessionStatus.DENIED)
            return {"status": SessionStatus.DENIED}

        graph = StateGraph(LasiState)
        graph.add_node("retrieve", retrieve)
        graph.add_node("pressure", pressure)
        graph.add_node("plan", plan)
        graph.add_node("verify", verify)
        graph.add_node("request_approval", request_approval)
        graph.add_node("approval", approval)
        graph.add_node("execute", execute)
        graph.add_node("denied", denied)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "pressure")
        graph.add_edge("pressure", "plan")
        graph.add_edge("plan", "verify")
        graph.add_conditional_edges(
            "verify",
            route,
            {
                "execute": "execute",
                "request_approval": "request_approval",
                "denied": "denied",
            },
        )
        graph.add_edge("request_approval", "approval")
        graph.add_edge("approval", "verify")
        graph.add_edge("execute", END)
        graph.add_edge("denied", END)
        return graph.compile(checkpointer=checkpointer)


class LasiRuntime:
    def __init__(
        self,
        *,
        graph: Any,
        store: AuthorityStore,
        identities: IdentityService,
        approvals: ApprovalService,
        owner_id: str | None = None,
    ) -> None:
        self.graph = graph
        self.store = store
        self.identities = identities
        self.approvals = approvals
        self.owner_id = owner_id or str(uuid4())
        self._active: dict[str, asyncio.Task[dict[str, Any]]] = {}
        if not store.acquire_lease(self.owner_id):
            raise RuntimeError("another LASI coordinator holds the authority lease")

    async def start(self, goal: Goal, signed_action: SignedAction) -> dict[str, Any]:
        self._require_lease()
        principal = self.identities.authenticate(
            signed_action, expected_action="start_goal", expected_payload=goal
        )
        session_id = str(uuid4())
        thread_id = str(uuid4())
        self.store.start_session(session_id, thread_id, goal, principal.subject_id)
        config = {"configurable": {"thread_id": thread_id}}
        task = asyncio.create_task(
            self.graph.ainvoke(
                {
                    "session_id": session_id,
                    "requester_id": principal.subject_id,
                    "goal": goal,
                    "status": SessionStatus.PLANNING,
                },
                config=config,
            )
        )
        self._active[session_id] = task
        try:
            return await self._with_heartbeat(task)
        finally:
            self._active.pop(session_id, None)

    async def resume(self, session_id: str, signed_action: SignedAction) -> dict[str, Any]:
        from langgraph.types import Command

        self._require_lease()
        session = self.store.session(session_id)
        if session is None:
            raise KeyError("session does not exist")
        principal = self.identities.authenticate(
            signed_action,
            expected_action="resume_session",
            expected_payload={"session_id": session_id},
        )
        if principal.subject_id != session["requester_id"] and "admin" not in principal.roles:
            raise PermissionError("only the requester or an administrator may resume")
        config = {"configurable": {"thread_id": session["thread_id"]}}
        task = asyncio.create_task(
            self.graph.ainvoke(Command(resume={"wake": True}), config=config)
        )
        self._active[session_id] = task
        try:
            return await self._with_heartbeat(task)
        finally:
            self._active.pop(session_id, None)

    def decide_approval(
        self,
        *,
        request_id: str,
        choice: ApprovalChoice,
        reason: str,
        signed_action: SignedAction,
    ) -> None:
        self.approvals.decide(
            request_id=request_id,
            choice=choice,
            reason=reason,
            signed_action=signed_action,
        )

    async def cancel(self, session_id: str, signed_action: SignedAction) -> None:
        payload = {"session_id": session_id}
        principal = self.identities.authenticate(
            signed_action, expected_action="cancel_session", expected_payload=payload
        )
        session = self.store.session(session_id)
        if session is None:
            raise KeyError("session does not exist")
        if principal.subject_id != session["requester_id"] and "admin" not in principal.roles:
            raise PermissionError("only the requester or an administrator may cancel")
        self.store.request_cancel(session_id)
        task = self._active.get(session_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def status(self, session_id: str, signed_action: SignedAction) -> dict[str, Any]:
        session = self.store.session(session_id)
        if session is None:
            raise KeyError("session does not exist")
        principal = self.identities.authenticate(
            signed_action,
            expected_action="inspect_session",
            expected_payload={"session_id": session_id},
        )
        if (
            principal.subject_id != session["requester_id"]
            and not {"admin", "auditor"} & principal.roles
        ):
            raise PermissionError("identity may not inspect this session")
        return session

    async def _with_heartbeat(self, task: asyncio.Task[dict[str, Any]]) -> dict[str, Any]:
        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(10)
                if not self.store.acquire_lease(self.owner_id):
                    task.cancel()
                    raise RuntimeError("coordinator lease was lost")

        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait(
                {task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat_task in done:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                await heartbeat_task
                raise RuntimeError("coordinator heartbeat ended unexpectedly")
            return await task
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    def _require_lease(self) -> None:
        if not self.store.acquire_lease(self.owner_id):
            raise RuntimeError("another LASI coordinator holds the authority lease")


@asynccontextmanager
async def sqlite_checkpointer(path: Path) -> AsyncIterator[Any]:
    """Open a private durable LangGraph SQLite checkpointer."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        path.chmod(0o600)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver
    path.chmod(0o600)
