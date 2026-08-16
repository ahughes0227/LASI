"""Durable workflow for a validated, governed component experiment graph."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from services.components import (
    ComponentGraphRunner,
    ComponentRegistry,
    ExperimentSpecResolver,
    ProtectedComponentExecution,
)
from services.context import ArtifactContract, ICMStore
from services.contracts import (
    ArtifactRecord,
    DecisionRecord,
    ExperimentPlan,
    ExperimentSpec,
    ProjectConfig,
    ReportSection,
)
from services.core import ArtifactStore
from services.experiments import compile_component_plan
from services.isolation import IsolationProfile, require_benchmark_isolation
from services.memory import OperationalMemory, Project
from services.reports import (
    ExperimentCloseoutError,
    ReportRenderer,
    build_experiment_closeout_report,
)
from services.telemetry import TokenUsageService


@dataclass(frozen=True)
class ComponentExperimentRequest:
    spec: ExperimentSpec
    reason_for_experiment: str
    expected_signal: str
    success_criteria: str
    failure_criteria: str
    decision: DecisionRecord | None = None
    benchmark_protected: bool = False
    isolation_profile: IsolationProfile | None = None
    protected_execution: ProtectedComponentExecution | None = None
    artifact_store: ArtifactStore | None = None
    project_config: ProjectConfig | None = None
    operational_memory: OperationalMemory | None = None
    eda_findings: ReportSection | None = None
    surprising_findings: ReportSection | None = None
    proposed_approaches: ReportSection | None = None


@dataclass(frozen=True)
class ComponentExperimentResult:
    plan: ExperimentPlan
    decision: DecisionRecord
    resolved_spec_path: Path
    run_root: Path
    output_refs: dict[str, Path]
    report_path: Path
    artifacts: tuple[ArtifactRecord, ...] = ()


def run_component_experiment(
    request: ComponentExperimentRequest,
    *,
    registry: ComponentRegistry,
    run_root: str | Path,
    icm_store: ICMStore | None = None,
) -> ComponentExperimentResult:
    """Resolve first, require authorization, then execute and record readable context."""
    execution_id = f"component-execution-{uuid4().hex}"
    metering, eda_findings, surprising_findings, proposed_approaches = _require_closeout_inputs(
        request, _initialize_metering(request)
    )
    resolved = ExperimentSpecResolver(registry).resolve(request.spec)
    _record_not_applicable(
        metering,
        request.spec.project_id,
        f"{execution_id}-resolution",
        "component_spec_resolution",
        "trusted local schema resolution does not invoke an LLM or token-metered runtime",
    )
    if request.benchmark_protected:
        if request.protected_execution is None:
            raise PermissionError(
                "protected component experiment requires a fail-closed protected execution policy"
            )
        require_benchmark_isolation(
            {
                "benchmark_protected": True,
                "isolation_profile": request.isolation_profile,
                "isolation_backend": "component-workflow-policy",
            }
        )
    plan = compile_component_plan(
        resolved,
        reason_for_experiment=request.reason_for_experiment,
        expected_signal=request.expected_signal,
        success_criteria=request.success_criteria,
        failure_criteria=request.failure_criteria,
        created_by=request.spec.provenance.author,
    )
    _record_not_applicable(
        metering,
        request.spec.project_id,
        f"{execution_id}-plan",
        "experiment_plan_compilation",
        "local deterministic plan compilation does not invoke an LLM or token-metered runtime",
    )
    if request.decision is None:
        raise PermissionError("component experiment requires an explicit decision record")
    _record_not_applicable(
        metering,
        request.spec.project_id,
        f"{execution_id}-decision",
        "decision_evaluation",
        "local deterministic decision evaluation does not invoke an LLM or token-metered runtime",
    )
    output = ComponentGraphRunner(registry).run(
        resolved,
        plan=plan,
        decision=request.decision,
        workdir=run_root,
        protected_execution=request.protected_execution,
    )
    for tool_run in output.tool_runs:
        _record_not_applicable(
            metering,
            request.spec.project_id,
            tool_run.tool_run_id,
            "component_execution",
            "trusted local component execution does not invoke an LLM or token-metered runtime",
        )
    if any(result.status != "succeeded" for result in output.tool_runs):
        failures = [result.tool_id for result in output.tool_runs if result.status != "succeeded"]
        raise RuntimeError(f"component graph did not complete: {failures}")
    if icm_store is not None:
        _record_icm(
            icm_store,
            request.spec,
            plan,
            output.resolved_spec_path,
            output.outputs,
            request.project_config,
        )
        _record_not_applicable(
            metering,
            request.spec.project_id,
            f"{execution_id}-project-context",
            "project_context_update",
            (
                "structured project-context persistence does not invoke an LLM "
                "or token-metered runtime"
            ),
        )
    artifacts = _persist_artifacts(request, plan, output.resolved_spec_path, output.outputs)
    if artifacts:
        _record_not_applicable(
            metering,
            request.spec.project_id,
            f"{execution_id}-artifact-persistence",
            "artifact_persistence",
            "local artifact persistence does not invoke an LLM or token-metered runtime",
        )
    _record_not_applicable(
        metering,
        request.spec.project_id,
        f"{execution_id}-report",
        "report_generation",
        "fixed-template report rendering does not invoke an LLM or token-metered runtime",
    )
    report = build_experiment_closeout_report(
        report_id=f"report-{request.spec.experiment_spec_id}-{uuid4().hex}",
        project=request.project_config
        or ProjectConfig(
            project_id=request.spec.project_id,
            project_name=request.spec.project_id,
            problem_type=request.spec.problem_type,
            modality=request.spec.modality,
        ),
        spec=request.spec,
        plan=plan,
        decision=request.decision,
        tool_runs=output.tool_runs,
        output_refs=output.outputs,
        eda_findings=eda_findings,
        surprising_findings=surprising_findings,
        proposed_approaches=proposed_approaches,
        token_usage=metering.project_report(request.spec.project_id),
    )
    report_path = _report_path(icm_store, request.spec, run_root, report.report_id)
    ReportRenderer().write_immutable(report, report_path)
    report_artifact = _persist_report_artifact(request, plan, report.report_id, report_path)
    if report_artifact is not None:
        artifacts = (*artifacts, report_artifact)
    if icm_store is not None:
        _record_report_reference(icm_store, request.spec, report_path)
        _write_telemetry_projection(icm_store, request.spec, metering)
    return ComponentExperimentResult(
        plan=plan,
        decision=request.decision,
        resolved_spec_path=output.resolved_spec_path,
        run_root=Path(run_root).resolve(),
        output_refs=output.outputs,
        report_path=report_path,
        artifacts=artifacts,
    )


def _initialize_metering(request: ComponentExperimentRequest) -> TokenUsageService | None:
    if request.operational_memory is None:
        return None
    project = request.project_config or ProjectConfig(
        project_id=request.spec.project_id,
        project_name=request.spec.project_id,
        problem_type=request.spec.problem_type,
        modality=request.spec.modality,
    )
    if not request.operational_memory.project_exists(project.project_id):
        request.operational_memory.add(
            Project(
                project_id=project.project_id,
                project_name=project.project_name,
                problem_type=project.problem_type,
                modality=project.modality,
                payload=project.model_dump(mode="json"),
            )
        )
    return TokenUsageService(request.operational_memory)


def _require_closeout_inputs(
    request: ComponentExperimentRequest, metering: TokenUsageService | None
) -> tuple[TokenUsageService, ReportSection, ReportSection, ReportSection]:
    if metering is None:
        raise ExperimentCloseoutError(
            "component experiment closeout requires operational memory for per-action telemetry"
        )
    if request.eda_findings is None or request.surprising_findings is None:
        raise ExperimentCloseoutError(
            "component experiment closeout requires EDA and surprising-findings sections"
        )
    if request.proposed_approaches is None:
        raise ExperimentCloseoutError("component experiment closeout requires approach evidence")
    return metering, request.eda_findings, request.surprising_findings, request.proposed_approaches


def _record_not_applicable(
    metering: TokenUsageService | None,
    project_id: str,
    action_id: str,
    action_type: str,
    reason: str,
) -> None:
    if metering is not None:
        metering.record_not_applicable(
            project_id=project_id,
            action_id=action_id,
            action_type=action_type,
            reason=reason,
        )


def _report_path(
    store: ICMStore | None, spec: ExperimentSpec, run_root: str | Path, report_id: str
) -> Path:
    if store is None:
        return Path(run_root).resolve().parent / report_id / "index.html"
    return (
        Path(store.project_root(spec.project_id))
        / "40_output"
        / "reports"
        / report_id
        / "index.html"
    )


def _record_report_reference(store: ICMStore, spec: ExperimentSpec, report_path: Path) -> None:
    relative = f"40_output/reports/{report_path.parent.name}.md"
    contract = ArtifactContract(capability="reporting", writes=[relative])
    store.write_artifact(
        spec.project_id,
        relative,
        f"# Experiment Closeout Report\n\nStatic report: {report_path}\n",
        contract=contract,
    )


def _write_telemetry_projection(
    store: ICMStore, spec: ExperimentSpec, metering: TokenUsageService
) -> None:
    """Write a readable projection; operational memory remains authoritative."""
    summary = metering.project_report(spec.project_id)
    records = metering.action_records(spec.project_id)
    document = {
        "project_id": spec.project_id,
        "authoritative_source": "operational_memory",
        "summary": {
            **summary.model_dump(mode="json"),
        },
        "actions": [
            {
                "action_usage_id": record.action_usage_id,
                "action_id": record.action_id,
                "action_type": record.action_type,
                "status": record.metering_status,
                "total_tokens": record.total_tokens,
                "billed_cost_usd": record.billed_cost_usd,
                "reason": record.unavailable_reason,
            }
            for record in records
        ],
    }
    contract = ArtifactContract(
        capability="telemetry",
        writes=[f"30_evidence/telemetry/{spec.experiment_spec_id}.json"],
    )
    store.write_artifact(
        spec.project_id,
        f"30_evidence/telemetry/{spec.experiment_spec_id}.json",
        json.dumps(document, indent=2, sort_keys=True),
        overwrite=True,
        contract=contract,
    )


def _persist_artifacts(
    request: ComponentExperimentRequest,
    plan: ExperimentPlan,
    resolved_spec_path: Path,
    outputs: dict[str, Path],
) -> tuple[ArtifactRecord, ...]:
    if request.artifact_store is None:
        return ()
    records: list[ArtifactRecord] = []
    with request.artifact_store.start_run(
        f"component-{plan.experiment_plan_id}",
        tags={"project_id": plan.project_id, "experiment_plan_id": plan.experiment_plan_id},
    ) as run:
        records.append(
            request.artifact_store.log_file(
                run,
                resolved_spec_path,
                artifact_type="resolved_experiment_spec",
                artifact_path="specs/resolved-experiment-spec.json",
                project_id=plan.project_id,
                dataset_version_id=plan.dataset_version,
                experiment_id=request.spec.experiment_spec_id,
            )
        )
        for output_id, source in sorted(outputs.items()):
            records.append(
                request.artifact_store.log_file(
                    run,
                    source,
                    artifact_type="component_output",
                    artifact_path=f"component-outputs/{output_id.replace('.', '/')}/{source.name}",
                    project_id=plan.project_id,
                    dataset_version_id=plan.dataset_version,
                    experiment_id=request.spec.experiment_spec_id,
                )
            )
    return tuple(records)


def _persist_report_artifact(
    request: ComponentExperimentRequest,
    plan: ExperimentPlan,
    report_id: str,
    report_path: Path,
) -> ArtifactRecord | None:
    if request.artifact_store is None:
        return None
    with request.artifact_store.start_run(
        f"report-{plan.experiment_plan_id}",
        tags={"project_id": plan.project_id, "experiment_plan_id": plan.experiment_plan_id},
    ) as run:
        return request.artifact_store.log_file(
            run,
            report_path,
            artifact_type="experiment_closeout_report",
            artifact_path=f"reports/{report_path.parent.name}/{report_path.name}",
            project_id=plan.project_id,
            dataset_version_id=plan.dataset_version,
            experiment_id=request.spec.experiment_spec_id,
            report_id=report_id,
        )


def _record_icm(
    store: ICMStore,
    spec: ExperimentSpec,
    plan: ExperimentPlan,
    resolved_path: Path,
    outputs: dict[str, Path],
    project_config: ProjectConfig | None,
) -> None:
    store.initialize_project(
        project_config
        or ProjectConfig(
            project_id=spec.project_id,
            project_name=spec.project_id,
            problem_type="classification",
            modality="tabular",
        )
    )
    root = f"20_work/experiments/{spec.experiment_spec_id}"
    contract = ArtifactContract(
        capability="modeling",
        writes=[
            f"{root}/hypothesis.md",
            f"{root}/config.yaml",
            f"{root}/inputs.md",
            f"{root}/results.md",
        ],
    )
    store.initialize_experiment(
        spec.project_id,
        spec.experiment_spec_id,
        hypothesis=spec.hypothesis,
        config=json.loads(resolved_path.read_text(encoding="utf-8")),
        inputs=[spec.dataset_version_id],
        contract=contract,
    )
    store.record_experiment_result(
        spec.project_id,
        spec.experiment_spec_id,
        status="succeeded",
        result=(f"Plan: {plan.experiment_plan_id}\nResolved spec: {resolved_path}\n"),
        artifact_refs=[str(path) for path in outputs.values()],
        contract=contract,
    )
