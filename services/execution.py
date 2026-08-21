"""Rigid, replay-safe executor for verified declarative plans."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from .contracts import (
    ExecutionResult,
    OperatorInvocation,
    OperatorResult,
    Plan,
    StepRun,
    VerificationResult,
)
from .ledger import SqliteLedger
from .operators import OperatorRegistry


class ExecutionDenied(RuntimeError):
    pass


class DeterministicExecutor:
    def __init__(self, registry: OperatorRegistry, ledger: SqliteLedger) -> None:
        self.registry = registry
        self.ledger = ledger

    def execute(self, plan: Plan, verification: VerificationResult) -> ExecutionResult:
        if (
            not verification.allowed
            or verification.plan_id != plan.plan_id
            or verification.plan_digest != plan.digest()
            or not self.ledger.covers_plan(plan, verification)
        ):
            raise ExecutionDenied("plan is not covered by a recorded allowed decision")

        run_id = str(uuid4())
        completed: dict[str, StepRun] = {}
        runs: list[StepRun] = []
        self.ledger.emit(
            plan.goal.project_id, "run_started", {"run_id": run_id, "plan_id": plan.plan_id}
        )
        for step in plan.steps:
            if any(completed[item].status != "succeeded" for item in step.depends_on):
                step_run = StepRun(step_id=step.step_id, operator=step.operator, status="blocked")
                completed[step.step_id] = step_run
                runs.append(step_run)
                continue
            registered = self.registry.get(step.operator)
            key_payload = {
                "plan": plan.digest(),
                "step": step.model_dump(mode="json"),
                "operator_version": registered.spec.version,
            }
            key = hashlib.sha256(
                json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            prior = self.ledger.successful_result(key) if registered.spec.idempotent else None
            if prior is not None:
                step_run = StepRun(
                    step_id=step.step_id,
                    operator=step.operator,
                    status=prior.status,
                    result=prior,
                    reused=True,
                )
            else:
                invocation = OperatorInvocation(
                    run_id=run_id,
                    project_id=plan.goal.project_id,
                    step=step,
                    idempotency_key=key,
                )
                try:
                    result = registered.invoke(invocation)
                except Exception as exc:
                    result = OperatorResult(
                        status="failed", failure_reason=f"{type(exc).__name__}: {exc}"
                    )
                self.ledger.record_operator_result(
                    idempotency_key=key, run_id=run_id, step_id=step.step_id, result=result
                )
                step_run = StepRun(
                    step_id=step.step_id,
                    operator=step.operator,
                    status=result.status,
                    result=result,
                )
            completed[step.step_id] = step_run
            runs.append(step_run)
            self.ledger.emit(
                plan.goal.project_id, "step_finished", step_run.model_dump(mode="json")
            )
        status = "succeeded" if all(item.status == "succeeded" for item in runs) else "failed"
        execution_result = ExecutionResult(
            run_id=run_id, plan_id=plan.plan_id, status=status, steps=tuple(runs)
        )
        self.ledger.emit(
            plan.goal.project_id,
            "run_finished",
            execution_result.model_dump(mode="json"),
        )
        return execution_result
