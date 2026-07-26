"""Local execution backend for registered tools."""

# fmt: off

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import uuid4

from lasi.contracts import DecisionRecord, ExperimentPlan, ToolRunResult

from .registry import ToolRegistry


@dataclass(frozen=True)
class ToolContext:
    project_id: str
    dataset_version_id: str
    tool_run_id: str
    experiment_id: str | None
    experiment_plan_id: str | None
    input_refs: tuple[str, ...]
    parameters: dict[str, Any]


@dataclass
class ToolOutput:
    output_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    partial_success: dict[str, Any] | None = None


class LocalToolRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def run(
        self,
        tool_id: str,
        project_id: str,
        dataset_version_id: str,
        *,
        plan: ExperimentPlan,
        decision: DecisionRecord,
        input_refs: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        experiment_id: str | None = None,
        experiment_plan_id: str | None = None,
        expected_version: str | None = None,
        timeout_seconds: float | None = None,
        requested_status: str | None = None,
        reason: str | None = None,
    ) -> ToolRunResult:
        self._require_matching_authorization(
            tool_id, project_id, dataset_version_id, experiment_plan_id, plan, decision,
            expected_version=expected_version, requested_parameters=parameters,
        )
        registered = self.registry.get(tool_id, expected_version)
        from lasi.isolation import require_benchmark_isolation

        require_benchmark_isolation(parameters or {})
        planned = next(item for item in plan.planned_tool_runs if item.tool_id == tool_id)
        effective_parameters = dict(planned.parameters) if parameters is None else parameters
        run_id = str(uuid4())
        start = datetime.now(UTC)
        started = monotonic()
        if requested_status in {"skipped", "blocked", "cancelled"}:
            return self._result(
                run_id,
                project_id,
                dataset_version_id,
                tool_id,
                registered.spec.version,
                input_refs,
                effective_parameters,
                experiment_id,
                experiment_plan_id,
                start,
                requested_status,
                datetime.now(UTC),
                0,
                failure_reason=reason or requested_status,
            )
        context = ToolContext(
            project_id,
            dataset_version_id,
            run_id,
            experiment_id,
            experiment_plan_id,
            tuple(input_refs or []),
            effective_parameters,
        )
        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[object] = executor.submit(registered.handler, context)
        try:
            raw = future.result(timeout=timeout_seconds)
            output = self._output(raw)
            status = "partial_success" if output.partial_success else "succeeded"
            return self._result(
                run_id,
                project_id,
                dataset_version_id,
                tool_id,
                registered.spec.version,
                input_refs,
                effective_parameters,
                experiment_id,
                experiment_plan_id,
                start,
                status,
                datetime.now(UTC),
                monotonic() - started,
                output_refs=output.output_refs,
                artifact_refs=output.artifact_refs,
                metrics=output.metrics,
                warnings=output.warnings,
                errors=output.errors,
                partial_success=output.partial_success,
            )
        except FutureTimeout:
            future.cancel()
            return self._result(
                run_id,
                project_id,
                dataset_version_id,
                tool_id,
                registered.spec.version,
                input_refs,
                effective_parameters,
                experiment_id,
                experiment_plan_id,
                start,
                "timed_out",
                datetime.now(UTC),
                monotonic() - started,
                errors=["tool timed out"],
                failure_reason=reason or "timeout",
            )
        except Exception as exc:  # noqa: BLE001 - tool failures are structured evidence.
            return self._result(
                run_id,
                project_id,
                dataset_version_id,
                tool_id,
                registered.spec.version,
                input_refs,
                effective_parameters,
                experiment_id,
                experiment_plan_id,
                start,
                "failed",
                datetime.now(UTC),
                monotonic() - started,
                errors=[str(exc)],
                failure_reason=reason or "tool_error",
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _require_matching_authorization(
        tool_id: str,
        project_id: str,
        dataset_version_id: str,
        experiment_plan_id: str | None,
        plan: ExperimentPlan,
        decision: DecisionRecord,
        *,
        expected_version: str | None,
        requested_parameters: dict[str, Any] | None,
    ) -> None:
        from lasi.experiments import require_allowed_decision

        if plan.project_id != project_id:
            raise PermissionError("experiment plan project does not match tool run")
        if plan.dataset_version != dataset_version_id:
            raise PermissionError("experiment plan dataset does not match tool run")
        if plan.execution_backend != "local":
            raise PermissionError("local tool runner requires a local experiment plan")
        if experiment_plan_id is not None and experiment_plan_id != plan.experiment_plan_id:
            raise PermissionError("tool run plan does not match the approved experiment plan")
        matching = [item for item in plan.planned_tool_runs if item.tool_id == tool_id]
        if not matching:
            raise PermissionError("tool is not included in the approved experiment plan")
        planned = matching[0]
        planned_version = planned.parameters.get("tool_version")
        if planned_version is not None and expected_version != planned_version:
            raise PermissionError("tool version does not match the approved experiment plan")
        if (
            planned.parameters
            and requested_parameters is not None
            and requested_parameters != planned.parameters
        ):
            raise PermissionError("tool parameters do not match the approved experiment plan")
        require_allowed_decision(plan, decision)

    @staticmethod
    def _result(
        run_id: str,
        project_id: str,
        dataset_version_id: str,
        tool_id: str,
        tool_version: str,
        input_refs: list[str] | None,
        parameters: dict[str, Any] | None,
        experiment_id: str | None,
        experiment_plan_id: str | None,
        start: datetime,
        status: str,
        end: datetime,
        runtime: float,
        *,
        output_refs: list[str] | None = None,
        artifact_refs: list[str] | None = None,
        metrics: dict[str, float | int | str | bool | None] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        failure_reason: str | None = None,
        partial_success: dict[str, Any] | None = None,
    ) -> ToolRunResult:
        return ToolRunResult(
            tool_run_id=run_id,
            project_id=project_id,
            experiment_id=experiment_id,
            experiment_plan_id=experiment_plan_id,
            dataset_version_id=dataset_version_id,
            tool_id=tool_id,
            tool_version=tool_version,
            input_refs=input_refs or [],
            parameters=parameters or {},
            execution_backend="local",
            status=status,
            start_time=start,
            end_time=end,
            runtime_seconds=runtime,
            output_refs=output_refs or [],
            artifact_refs=artifact_refs or [],
            metrics=metrics or {},
            warnings=warnings or [],
            errors=errors or [],
            failure_reason=failure_reason,
            partial_success=partial_success,
        )

    @staticmethod
    def _output(raw: object) -> ToolOutput:
        if raw is None:
            return ToolOutput()
        if isinstance(raw, ToolOutput):
            return raw
        if isinstance(raw, dict):
            return ToolOutput(**raw)
        raise TypeError("tool handler must return ToolOutput, dict, or None")
