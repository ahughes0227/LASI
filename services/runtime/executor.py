"""Generic runtime executor for leased SQL tasks and structured agent returns."""

from __future__ import annotations

from typing import Protocol

from services.contracts import AgentInvocationResult, AgentResult, AgentTask

from .task_runtime import TaskRuntimeService


class AgentInvoker(Protocol):
    def invoke(self, task: AgentTask) -> AgentInvocationResult: ...


class TaskExecutor:
    """Agents receive SQL-issued tasks; only the runtime commits their results."""

    def __init__(
        self, runtime: TaskRuntimeService, invoker: AgentInvoker, *, executor_id: str
    ) -> None:
        self.runtime = runtime
        self.invoker = invoker
        self.executor_id = executor_id

    def run_once(self, assignment_id: str) -> str:
        task = self.runtime.lease_ready_task(assignment_id, lease_owner=self.executor_id)
        if task is None:
            return "idle"
        try:
            invocation = self.invoker.invoke(task)
        except Exception as exc:  # invocation failures remain structured task evidence.
            invocation = AgentInvocationResult(
                result=AgentResult(
                    task_id=task.task.task_id,
                    attempt_id=task.attempt_id,
                    status="failed",
                    summary="Agent invocation failed before a valid result was returned.",
                    criterion_results=[],
                    failure_reason=str(exc),
                )
            )
        return self.runtime.submit_result(
            invocation.result,
            lease_owner=self.executor_id,
            usage=invocation.usage,
            raw_response_artifact_ref=invocation.raw_response_artifact_ref,
        )
