"""Validated local execution of a component graph with durable artifact edges."""

from __future__ import annotations

import contextvars
import inspect
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from services.contracts import DecisionRecord, ExperimentPlan, ToolRunResult
from services.experiments.execution import require_allowed_decision
from services.isolation import (
    BenchmarkIsolationError,
    IsolationProfile,
    require_benchmark_isolation,
)

from .registry import ComponentRegistry
from .specs import ResolvedExperimentSpec


@dataclass(frozen=True)
class ComponentExecutionContext:
    project_id: str
    dataset_version_id: str
    experiment_spec_id: str
    node_id: str
    workdir: Path
    inputs: dict[str, Path]
    config: Any
    random_seed: int | None


@dataclass
class ComponentRunOutput:
    outputs: dict[str, Path] = field(default_factory=dict)
    metrics: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ComponentRunResult:
    resolved_spec: ResolvedExperimentSpec
    tool_runs: tuple[ToolRunResult, ...]
    outputs: dict[str, Path]
    resolved_spec_path: Path


@dataclass(frozen=True)
class ProtectedComponentExecution:
    """Fail-closed policy for a trusted project-local protected component graph.

    This is intentionally an execution policy, rather than component supplied
    configuration: handlers cannot weaken it.  The component's source hash must
    be declared by the caller that performs the project-scoped registration.
    """

    profile: IsolationProfile
    source_hashes: dict[str, str]
    max_cpu_seconds: int
    max_wall_seconds: int
    max_memory_bytes: int

    def validate(self) -> None:
        require_benchmark_isolation(
            {
                "benchmark_protected": True,
                "isolation_profile": self.profile,
                "isolation_backend": "protected-component-audit-hook-v1",
            }
        )
        if not self.profile.allowed_read_paths or not self.profile.allowed_write_paths:
            raise BenchmarkIsolationError("protected components require read and write allowlists")
        if min(self.max_cpu_seconds, self.max_wall_seconds, self.max_memory_bytes) <= 0:
            raise ValueError("protected component resources must be positive")


_ACTIVE_PROTECTED_POLICY: contextvars.ContextVar[ProtectedComponentExecution | None] = (
    contextvars.ContextVar("active_protected_component_policy", default=None)
)
_AUDIT_HOOK_INSTALLED = False


def _under(path: Path, roots: tuple[str, ...]) -> bool:
    resolved = path.resolve(strict=False)
    return any(
        resolved == Path(root).resolve() or Path(root).resolve() in resolved.parents
        for root in roots
    )


def _audit_hook(event: str, args: tuple[object, ...]) -> None:
    policy = _ACTIVE_PROTECTED_POLICY.get()
    if policy is None:
        return
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        raise BenchmarkIsolationError("network access is denied for protected component execution")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise BenchmarkIsolationError(
            "subprocess access is denied for protected component execution"
        )
    if event in {"os.mkdir", "os.rmdir", "os.remove", "os.unlink"} and args:
        if isinstance(args[0], (str, bytes, os.PathLike)) and not _under(
            Path(args[0]), policy.profile.allowed_write_paths
        ):
            raise BenchmarkIsolationError(
                f"protected component filesystem mutation escapes allowlist: {args[0]}"
            )
    if event in {"os.rename", "os.replace"} and len(args) >= 2:
        paths = [Path(value) for value in args[:2] if isinstance(value, (str, bytes, os.PathLike))]
        if any(not _under(path, policy.profile.allowed_write_paths) for path in paths):
            raise BenchmarkIsolationError("protected component rename escapes write allowlist")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(args[0])
        mode = str(args[1]) if len(args) > 1 else "r"
        writing = any(flag in mode for flag in "wax+")
        roots = policy.profile.allowed_write_paths if writing else policy.profile.allowed_read_paths
        # Interpreter and dependency modules are loaded from its trusted runtime;
        # component artifact reads still remain confined to declared roots.
        if not writing and any(part in {"lib", "site-packages"} for part in path.parts):
            return
        if not _under(path, roots):
            verb = "write" if writing else "read"
            raise BenchmarkIsolationError(f"protected component {verb} escapes allowlist: {path}")


def _install_audit_hook() -> None:
    global _AUDIT_HOOK_INSTALLED
    if not _AUDIT_HOOK_INSTALLED:
        sys.addaudithook(_audit_hook)
        _AUDIT_HOOK_INSTALLED = True


class _ProtectedExecutionScope:
    """Scoped audit enforcement and POSIX soft resource limits for trusted code."""

    def __init__(self, policy: ProtectedComponentExecution) -> None:
        self.policy = policy
        self.token: contextvars.Token[ProtectedComponentExecution | None] | None = None
        self.limits: list[tuple[int, tuple[int, int]]] = []
        self.old_alarm: tuple[float, float] | None = None
        self.old_alarm_handler: object | None = None

    def __enter__(self) -> None:
        self.policy.validate()
        _install_audit_hook()
        self.token = _ACTIVE_PROTECTED_POLICY.set(self.policy)
        if os.name == "posix":
            self.old_alarm_handler = signal.signal(signal.SIGALRM, self._timeout)
            self.old_alarm = signal.setitimer(signal.ITIMER_REAL, self.policy.max_wall_seconds)
        if os.name == "posix":
            import resource

            if sys.platform == "darwin":
                # Python's Darwin resource module aliases RLIMIT_AS to RSS and
                # cannot lower the inherited memory ceiling reliably.  Do not
                # claim that an in-process policy provides a memory boundary.
                raise BenchmarkIsolationError(
                    "protected component memory enforcement is unavailable on Darwin"
                )
            memory_limit = resource.RLIMIT_DATA if sys.platform == "darwin" else resource.RLIMIT_AS
            for limit, value in (
                (resource.RLIMIT_CPU, self.policy.max_cpu_seconds),
                (memory_limit, self.policy.max_memory_bytes),
            ):
                old = resource.getrlimit(limit)
                # macOS can expose an inherited soft limit above a finite hard
                # limit.  Do not mutate an invalid pair shared by the harness.
                if (
                    old[0] != resource.RLIM_INFINITY
                    and old[1] != resource.RLIM_INFINITY
                    and old[0] > old[1]
                ):
                    continue
                bounded = value if old[1] == resource.RLIM_INFINITY else min(value, old[1])
                if old[0] == resource.RLIM_INFINITY or bounded < old[0]:
                    try:
                        resource.setrlimit(limit, (bounded, old[1]))
                    except (OSError, ValueError) as exc:
                        raise BenchmarkIsolationError(
                            f"cannot enforce protected resource limit {limit}: {exc}"
                        ) from exc
                    self.limits.append((limit, old))

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.old_alarm is not None:
            signal.setitimer(signal.ITIMER_REAL, *self.old_alarm)
            if self.old_alarm_handler is not None:
                signal.signal(signal.SIGALRM, self.old_alarm_handler)
        if os.name == "posix":
            import resource

            for limit, old in reversed(self.limits):
                # Some POSIX implementations report an unlimited soft limit
                # with a finite hard limit; restoring that invalid pair fails.
                restored_soft = old[0] if old[1] == resource.RLIM_INFINITY else min(old[0], old[1])
                resource.setrlimit(limit, (restored_soft, old[1]))
        # Leave auditing active until the runner verifies and records the handler
        # outputs.  Reset after the node's complete contract boundary instead.

    @staticmethod
    def _timeout(signum: int, frame: object) -> None:
        raise TimeoutError("protected component exceeded its wall-time limit")


class ComponentGraphRunner:
    """Runs a frozen graph only after a matching governed plan is allowed."""

    def __init__(self, registry: ComponentRegistry) -> None:
        self.registry = registry

    def run(
        self,
        resolved: ResolvedExperimentSpec,
        *,
        plan: ExperimentPlan,
        decision: DecisionRecord,
        workdir: str | Path,
        protected_execution: ProtectedComponentExecution | None = None,
    ) -> ComponentRunResult:
        require_allowed_decision(plan, decision)
        self._validate_plan(resolved, plan)
        root = Path(workdir).resolve()
        if protected_execution is not None:
            protected_execution.validate()
            if not _under(root, protected_execution.profile.allowed_write_paths):
                raise BenchmarkIsolationError(
                    "component run root is outside protected write allowlist"
                )
        root.mkdir(parents=True, exist_ok=False)
        resolved_path = root / "resolved-experiment-spec.json"
        resolved_path.write_bytes(resolved.json_bytes())
        outputs: dict[str, Path] = {}
        runs: list[ToolRunResult] = []
        for node in resolved.resolved["component_graph"]:
            node_root = root / node["node_id"]
            node_root.mkdir()
            registered = self.registry.get(node["component_id"], node["component_version"])
            if protected_execution is not None:
                self._validate_protected_binding(registered, protected_execution)
            inputs = {
                name: self._resolve_input(ref, outputs) for name, ref in node["inputs"].items()
            }
            config = registered.config_model.model_validate(node["config"])
            run_id = f"component-run-{uuid4().hex}"
            started_at = datetime.now(UTC)
            started = monotonic()
            try:
                context = ComponentExecutionContext(
                    project_id=resolved.spec.project_id,
                    dataset_version_id=resolved.spec.dataset_version_id,
                    experiment_spec_id=resolved.spec.experiment_spec_id,
                    node_id=node["node_id"],
                    workdir=node_root,
                    inputs=inputs,
                    config=config,
                    random_seed=resolved.spec.random_seed,
                )
                if protected_execution is not None:
                    if not _under(node_root, protected_execution.profile.allowed_write_paths):
                        raise BenchmarkIsolationError(
                            "component workdir is outside protected write allowlist"
                        )
                    if any(
                        not _under(path, protected_execution.profile.allowed_read_paths)
                        for path in inputs.values()
                    ):
                        raise BenchmarkIsolationError(
                            "component input is outside protected read allowlist"
                        )
                    with _ProtectedExecutionScope(protected_execution):
                        raw = registered.handler(context)
                else:
                    raw = registered.handler(context)
                output = self._output(raw)
                expected = {port.name for port in registered.spec.outputs}
                unexpected = set(output.outputs) - expected
                missing = {port.name for port in registered.spec.outputs if port.required} - set(
                    output.outputs
                )
                if unexpected or missing:
                    raise ValueError(
                        f"component output contract violation; unexpected={sorted(unexpected)}, "
                        f"missing={sorted(missing)}"
                    )
                refs: list[str] = []
                for name, path in output.outputs.items():
                    resolved_path_value = path.resolve()
                    if node_root not in resolved_path_value.parents:
                        raise ValueError(f"component output escapes its workdir: {name}")
                    if not resolved_path_value.is_file():
                        raise FileNotFoundError(
                            f"component output is missing: {resolved_path_value}"
                        )
                    outputs[f"{node['node_id']}.{name}"] = resolved_path_value
                    refs.append(str(resolved_path_value))
                runs.append(
                    ToolRunResult(
                        tool_run_id=run_id,
                        project_id=resolved.spec.project_id,
                        experiment_id=resolved.spec.experiment_spec_id,
                        experiment_plan_id=plan.experiment_plan_id,
                        dataset_version_id=resolved.spec.dataset_version_id,
                        tool_id=registered.spec.component_id,
                        tool_version=registered.spec.version,
                        input_refs=[str(path) for path in inputs.values()],
                        output_refs=refs,
                        parameters=config.model_dump(mode="json", exclude_none=True),
                        execution_backend=resolved.spec.execution_backend,
                        status="succeeded",
                        start_time=started_at,
                        end_time=datetime.now(UTC),
                        runtime_seconds=monotonic() - started,
                        artifact_refs=refs,
                        metrics=output.metrics,
                        warnings=output.warnings,
                    )
                )
                if protected_execution is not None:
                    _ACTIVE_PROTECTED_POLICY.set(None)
            except Exception as exc:  # failures are evidence, not swallowed errors.
                if protected_execution is not None:
                    _ACTIVE_PROTECTED_POLICY.set(None)
                runs.append(
                    ToolRunResult(
                        tool_run_id=run_id,
                        project_id=resolved.spec.project_id,
                        experiment_id=resolved.spec.experiment_spec_id,
                        experiment_plan_id=plan.experiment_plan_id,
                        dataset_version_id=resolved.spec.dataset_version_id,
                        tool_id=registered.spec.component_id,
                        tool_version=registered.spec.version,
                        input_refs=[str(path) for path in inputs.values()],
                        parameters=config.model_dump(mode="json", exclude_none=True),
                        execution_backend=resolved.spec.execution_backend,
                        status="failed",
                        start_time=started_at,
                        end_time=datetime.now(UTC),
                        runtime_seconds=monotonic() - started,
                        errors=[str(exc)],
                        failure_reason="component_error",
                    )
                )
                break
        return ComponentRunResult(
            resolved_spec=resolved,
            tool_runs=tuple(runs),
            outputs=outputs,
            resolved_spec_path=resolved_path,
        )

    @staticmethod
    def _validate_plan(resolved: ResolvedExperimentSpec, plan: ExperimentPlan) -> None:
        if plan.project_id != resolved.spec.project_id:
            raise PermissionError("plan project does not match component experiment")
        if plan.dataset_version != resolved.spec.dataset_version_id:
            raise PermissionError("plan dataset does not match component experiment")
        if plan.execution_backend != resolved.spec.execution_backend:
            raise PermissionError("plan backend does not match component experiment")
        if not plan.planned_tool_runs or plan.planned_tool_runs[0].tool_id != "component_pipeline":
            raise PermissionError("plan does not authorize a component pipeline")
        planned_hash = plan.planned_tool_runs[0].parameters.get("resolved_spec_hash")
        if planned_hash != resolved.content_hash:
            raise PermissionError("plan does not authorize this resolved component specification")

    @staticmethod
    def _resolve_input(ref: str, outputs: dict[str, Path]) -> Path:
        if ref in outputs:
            return outputs[ref]
        path = Path(ref).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"external component input is missing: {path}")
        return path

    @staticmethod
    def _output(raw: object) -> ComponentRunOutput:
        if isinstance(raw, ComponentRunOutput):
            return raw
        if isinstance(raw, dict):
            return ComponentRunOutput(**raw)
        raise TypeError("component handler must return ComponentRunOutput or a mapping")

    @staticmethod
    def _validate_protected_binding(
        registered: object, policy: ProtectedComponentExecution
    ) -> None:
        handler = registered.handler
        component_id = registered.spec.component_id
        expected = policy.source_hashes.get(component_id)
        source = inspect.getsourcefile(handler)
        if expected is None or source is None or registered.source_hash is None:
            raise BenchmarkIsolationError(
                "protected component lacks a statically bound source hash"
            )
        observed = f"sha256:{sha256(Path(source).read_bytes()).hexdigest()}"
        if observed != expected or registered.source_hash != expected:
            raise BenchmarkIsolationError(
                "protected component source hash does not match registration"
            )
