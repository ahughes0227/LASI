"""Async, sequential, replay-safe subprocess execution."""

from __future__ import annotations

import asyncio
import hashlib
import os
import signal
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifacts import ArtifactStore
from .contracts import (
    ExecutionResult,
    OperatorResult,
    Plan,
    SessionStatus,
    StepRun,
    StepStatus,
    VerificationResult,
    canonical_json,
)
from .ledger import AuthorityStore
from .operators import OperatorRegistry, RegisteredOperator
from .policy import PlanVerifier


class ExecutionDenied(RuntimeError):
    pass


def _resource_limits(spec: Any) -> Any:
    if os.name != "posix":
        return None

    def apply() -> None:
        import resource

        memory = spec.max_memory_mb * 1024 * 1024
        output = spec.max_output_bytes * 2
        limits = (
            (resource.RLIMIT_AS, memory),
            (resource.RLIMIT_FSIZE, output),
            (resource.RLIMIT_CPU, max(1, int(spec.timeout_seconds) + 1)),
        )
        for kind, requested in limits:
            try:
                _, hard = resource.getrlimit(kind)
                value = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
                resource.setrlimit(kind, (value, value))
            except (OSError, ValueError):
                continue

    return apply


class SubprocessOperatorRunner:
    def __init__(self, runtime_root: Path, artifacts: ArtifactStore) -> None:
        self.runtime_root = runtime_root
        self.artifacts = artifacts
        runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    async def run(
        self,
        registered: RegisteredOperator,
        *,
        run_id: str,
        project_id: str,
        step: Any,
        idempotency_key: str,
    ) -> OperatorResult:
        spec = registered.spec
        try:
            arguments = registered.validate_input(step.arguments)
        except Exception as exc:
            return OperatorResult(
                status=StepStatus.FAILED,
                failure_code="invalid_input",
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
        workspace = self.runtime_root / run_id / step.step_id
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        invocation_path = workspace / "invocation.json"
        result_path = workspace / "result.json"
        invocation_path.write_text(
            canonical_json(
                {
                    "run_id": run_id,
                    "project_id": project_id,
                    "step_id": step.step_id,
                    "idempotency_key": idempotency_key,
                    "entrypoint": spec.entrypoint,
                    "arguments": arguments,
                }
            )
        )
        os.chmod(invocation_path, 0o600)
        stdout_path = workspace / "stdout.log"
        stderr_path = workspace / "stderr.log"
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in spec.environment_keys or key in {"PATH", "LANG", "LC_ALL", "TMPDIR"}
        }
        environment["PYTHONUNBUFFERED"] = "1"
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "services.operator_worker",
                str(invocation_path),
                str(result_path),
                cwd=workspace,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                preexec_fn=_resource_limits(spec),
                start_new_session=True,
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=spec.timeout_seconds)
            except TimeoutError:
                await self._terminate(process)
                return OperatorResult(
                    status=StepStatus.FAILED,
                    failure_code="timeout",
                    failure_reason=f"operator exceeded {spec.timeout_seconds} seconds",
                )
            except asyncio.CancelledError:
                await self._terminate(process)
                return OperatorResult(
                    status=StepStatus.CANCELLED,
                    failure_code="cancelled",
                    failure_reason="operator was cancelled",
                )
        if not result_path.exists():
            status = (
                StepStatus.RECONCILIATION_REQUIRED if not spec.idempotent else StepStatus.FAILED
            )
            return OperatorResult(
                status=status,
                failure_code="missing_result",
                failure_reason=f"operator exited {process.returncode} without a result",
            )
        if result_path.stat().st_size > spec.max_output_bytes:
            return OperatorResult(
                status=StepStatus.FAILED,
                failure_code="output_too_large",
                failure_reason="operator result exceeded its output limit",
            )
        try:
            result = OperatorResult.model_validate_json(result_path.read_text())
            outputs = registered.validate_output(result.outputs)
            raw_paths = outputs.pop("artifact_paths", list(result.artifact_paths))
            if not isinstance(raw_paths, (list, tuple)):
                raise TypeError("artifact_paths must be a list")
            paths: tuple[str, ...] = tuple(str(path) for path in raw_paths)
            receipts = tuple(self.artifacts.promote(path, workspace) for path in paths)
            return result.model_copy(
                update={"outputs": outputs, "artifact_paths": (), "artifacts": receipts}
            )
        except Exception as exc:
            return OperatorResult(
                status=StepStatus.FAILED,
                failure_code="invalid_result",
                failure_reason=f"{type(exc).__name__}: {exc}",
            )

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


class DeterministicExecutor:
    def __init__(
        self,
        registry: OperatorRegistry,
        store: AuthorityStore,
        verifier: PlanVerifier,
        runner: SubprocessOperatorRunner,
    ) -> None:
        self.registry = registry
        self.store = store
        self.verifier = verifier
        self.runner = runner

    async def execute(self, plan: Plan, verification: VerificationResult) -> ExecutionResult:
        current = self.verifier.verify(plan)
        self.store.record_decision(current)
        if (
            not verification.allowed
            or not current.allowed
            or current.plan_digest != verification.plan_digest
            or current.policy_version != verification.policy_version
        ):
            raise ExecutionDenied("execution-time authorization failed")
        run_id = str(uuid4())
        self.store.start_run(run_id, plan)
        completed: dict[str, StepRun] = {}
        runs: list[StepRun] = []
        for step in plan.steps:
            if any(completed[item].status != StepStatus.SUCCEEDED for item in step.depends_on):
                step_run = StepRun(
                    step_id=step.step_id, operator=step.operator, status=StepStatus.BLOCKED
                )
                completed[step.step_id] = step_run
                runs.append(step_run)
                continue
            registered = self.registry.get(step.operator)
            key = hashlib.sha256(
                canonical_json(
                    {
                        "plan": plan.digest(),
                        "step": step,
                        "operator_version": registered.spec.version,
                        "implementation": registered.spec.implementation_digest,
                    }
                ).encode()
            ).hexdigest()
            prior = self.store.successful_result(key) if registered.spec.idempotent else None
            if prior:
                step_run = StepRun(
                    step_id=step.step_id,
                    operator=step.operator,
                    status=StepStatus.SUCCEEDED,
                    result=prior,
                    reused=True,
                )
            else:
                self.store.record_step(
                    run_id=run_id,
                    step_id=step.step_id,
                    operator=step.operator,
                    status=StepStatus.RUNNING,
                    idempotency_key=key,
                )
                result = await self.runner.run(
                    registered,
                    run_id=run_id,
                    project_id=plan.goal.project_id,
                    step=step,
                    idempotency_key=key,
                )
                self.store.record_step(
                    run_id=run_id,
                    step_id=step.step_id,
                    operator=step.operator,
                    status=result.status,
                    idempotency_key=key,
                    result=result,
                )
                step_run = StepRun(
                    step_id=step.step_id,
                    operator=step.operator,
                    status=result.status,
                    result=result,
                )
            completed[step.step_id] = step_run
            runs.append(step_run)
            if step_run.status in {
                StepStatus.CANCELLED,
                StepStatus.RECONCILIATION_REQUIRED,
            }:
                break
        if any(item.status == StepStatus.RECONCILIATION_REQUIRED for item in runs):
            status = SessionStatus.RECONCILIATION_REQUIRED
        elif any(item.status == StepStatus.CANCELLED for item in runs):
            status = SessionStatus.CANCELLED
        elif all(item.status == StepStatus.SUCCEEDED for item in runs):
            status = SessionStatus.SUCCEEDED
        else:
            status = SessionStatus.FAILED
        self.store.finish_run(run_id, plan, status)
        return ExecutionResult(
            run_id=run_id,
            plan_id=plan.plan_id,
            status=status,
            steps=tuple(runs),
        )
