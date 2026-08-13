"""Tests for the typed component graph execution surface."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import BaseModel
from services.components import (
    ComponentGraphRunner,
    ComponentPromotionProposal,
    ComponentPromotionService,
    ComponentRegistry,
    ComponentReviewContext,
    ComponentReviewService,
    ExperimentSpecResolver,
    ProtectedComponentExecution,
    register_tabular_components,
)
from services.context import ICMStore
from services.contracts import (
    ApprovalRecord,
    ComponentRequest,
    ComponentSpec,
    DecisionRecord,
    ExperimentSpec,
    ReportSection,
)
from services.core import MlflowArtifactStore
from services.experiments import compile_component_plan
from services.isolation import IsolationProfile
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.reports import ExperimentCloseoutError
from services.telemetry import TokenUsageService
from services.workflows import ComponentExperimentRequest, run_component_experiment


def _spec(tmp_path: Path) -> ExperimentSpec:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    train.write_text(
        "PassengerId,Age,Sex,Survived\n1,22,male,0\n2,38,female,1\n3,26,female,1\n"
        "4,35,male,0\n5,28,female,1\n6,2,male,0\n7,54,male,0\n8,27,female,1\n"
        "9,14,female,1\n10,40,male,0\n",
        encoding="utf-8",
    )
    test.write_text("PassengerId,Age,Sex\n11,30,male\n12,20,female\n", encoding="utf-8")
    return ExperimentSpec(
        experiment_spec_id="tabular-test",
        project_id="component-project",
        dataset_version_id="titanic:v1",
        hypothesis="A naive linear baseline produces a reproducible evidence floor.",
        modality="tabular",
        problem_type="classification",
        random_seed=7,
        expected_outputs=["test_predictions"],
        component_graph=[
            {
                "node_id": "data",
                "component_id": "tabular_csv_dataset",
                "component_version": "1.0",
                "config": {
                    "train_path": str(train),
                    "test_path": str(test),
                    "target_column": "Survived",
                },
            },
            {
                "node_id": "split",
                "component_id": "stratified_holdout",
                "component_version": "1.0",
                "config": {"validation_fraction": 0.2, "seed": 7},
                "inputs": {"dataset": "data.dataset"},
            },
            {
                "node_id": "model",
                "component_id": "naive_logistic_classifier",
                "component_version": "1.0",
                "config": {},
                "inputs": {"dataset": "data.dataset", "split": "split.split"},
            },
            {
                "node_id": "evaluate",
                "component_id": "classification_evaluator",
                "component_version": "1.0",
                "config": {},
                "inputs": {"validation_predictions": "model.validation_predictions"},
            },
        ],
    )


def _decision(plan_id: str) -> DecisionRecord:
    return DecisionRecord(
        decision_id="decision-components",
        project_id="component-project",
        experiment_plan_id=plan_id,
        risk_level="low",
        decision="allow",
        allowed=True,
        rationale="bounded local baseline",
    )


def test_component_graph_resolves_defaults_and_runs(tmp_path: Path) -> None:
    registry = register_tabular_components(ComponentRegistry())
    resolved = ExperimentSpecResolver(registry).resolve(_spec(tmp_path))
    plan = compile_component_plan(
        resolved,
        reason_for_experiment="Establish a baseline.",
        expected_signal="A score and valid test predictions are produced.",
        success_criteria="All four components succeed.",
        failure_criteria="Any component fails.",
    )
    result = ComponentGraphRunner(registry).run(
        resolved, plan=plan, decision=_decision(plan.experiment_plan_id), workdir=tmp_path / "run"
    )

    assert len(result.tool_runs) == 4
    assert all(run.status == "succeeded" for run in result.tool_runs)
    assert result.resolved_spec_path.is_file()
    assert result.outputs["model.test_predictions"].is_file()
    assert result.outputs["evaluate.evaluation"].is_file()


def test_component_graph_rejects_incompatible_artifact_edges(tmp_path: Path) -> None:
    registry = register_tabular_components(ComponentRegistry())
    spec = _spec(tmp_path)
    invalid = spec.model_copy(
        update={
            "component_graph": [
                *spec.component_graph[:1],
                spec.component_graph[3].model_copy(
                    update={"inputs": {"validation_predictions": "data.dataset"}}
                ),
            ]
        }
    )
    with pytest.raises(ValueError, match="incompatible edge"):
        ExperimentSpecResolver(registry).resolve(invalid)


def test_component_workflow_writes_icm_and_immutable_artifacts(tmp_path: Path) -> None:
    registry = register_tabular_components(ComponentRegistry())
    spec = _spec(tmp_path)
    resolved = ExperimentSpecResolver(registry).resolve(spec)
    plan = compile_component_plan(
        resolved,
        reason_for_experiment="Establish a baseline.",
        expected_signal="A score is produced.",
        success_criteria="All components succeed.",
        failure_criteria="Any component fails.",
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    result = run_component_experiment(
        ComponentExperimentRequest(
            spec=spec,
            reason_for_experiment=plan.reason_for_experiment,
            expected_signal=plan.expected_signal,
            success_criteria=plan.success_criteria,
            failure_criteria=plan.failure_criteria,
            decision=_decision(plan.experiment_plan_id),
            artifact_store=MlflowArtifactStore(tmp_path / "mlruns"),
            operational_memory=memory,
            eda_findings=ReportSection(section_status="complete", summary="EDA complete."),
            surprising_findings=ReportSection(section_status="complete", summary="No surprises."),
            proposed_approaches=ReportSection(
                section_status="complete", summary="Baseline rationale."
            ),
        ),
        registry=registry,
        run_root=tmp_path / "workflow-run",
        icm_store=ICMStore(tmp_path / "icm"),
    )

    assert len(result.artifacts) == 8
    assert all(record.artifact_uri.startswith("runs:/") for record in result.artifacts)
    project_root = tmp_path / "icm" / "projects" / spec.project_id
    assert (
        project_root / "20_work" / "experiments" / spec.experiment_spec_id / "config.yaml"
    ).is_file()
    assert (
        project_root / "30_evidence" / "telemetry" / f"{spec.experiment_spec_id}.json"
    ).is_file()
    telemetry_projection = json.loads(
        (project_root / "30_evidence" / "telemetry" / f"{spec.experiment_spec_id}.json").read_text()
    )
    assert telemetry_projection["summary"]["input_tokens"] == 0
    assert telemetry_projection["summary"]["output_tokens"] == 0
    usage = TokenUsageService(memory).project_summary(spec.project_id)
    assert usage.total_tokens == 0
    assert usage.not_applicable_action_count == 10
    assert result.report_path.is_file()


def test_component_workflow_blocks_execution_without_closeout_inputs(tmp_path: Path) -> None:
    registry = register_tabular_components(ComponentRegistry())
    spec = _spec(tmp_path)
    resolved = ExperimentSpecResolver(registry).resolve(spec)
    plan = compile_component_plan(
        resolved,
        reason_for_experiment="Establish a baseline.",
        expected_signal="A score is produced.",
        success_criteria="All components succeed.",
        failure_criteria="Any component fails.",
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))

    with pytest.raises(ExperimentCloseoutError, match="EDA"):
        run_component_experiment(
            ComponentExperimentRequest(
                spec=spec,
                reason_for_experiment=plan.reason_for_experiment,
                expected_signal=plan.expected_signal,
                success_criteria=plan.success_criteria,
                failure_criteria=plan.failure_criteria,
                decision=_decision(plan.experiment_plan_id),
                operational_memory=memory,
            ),
            registry=registry,
            run_root=tmp_path / "blocked-run",
        )

    assert not (tmp_path / "blocked-run").exists()


def test_component_promotion_requires_human_toolbox_approval() -> None:
    class NovelConfig(BaseModel):
        value: int = 1

    registry = ComponentRegistry()
    proposal = ComponentPromotionProposal(
        proposal_id="component-promotion-1",
        project_id="component-project",
        component=ComponentSpec(
            component_id="novel_component",
            name="Novel component",
            version="1.0",
            lifecycle="draft",
        ),
        source_experiment_ids=("exp-1",),
        evidence_refs=("runs:/exp-1/evaluation.json",),
        test_refs=("tests/test_novel_component.py",),
        dependency_review_ref="review:dependencies",
        code_review_ref="review:code",
    )
    rejected = ApprovalRecord(
        approval_id="approval-1",
        project_id="component-project",
        action_type="update_toolbox",
        risk_level="high",
        requested_by="agent",
        approval_status="pending",
        created_at=datetime.now(UTC),
    )
    with pytest.raises(PermissionError, match="human approval"):
        ComponentPromotionService.approve_and_register(
            proposal, rejected, registry, NovelConfig, lambda _: {}
        )

    approved = rejected.model_copy(update={"approval_status": "approved", "approved_by": "owner"})
    registered = ComponentPromotionService.approve_and_register(
        proposal, approved, registry, NovelConfig, lambda _: {}
    )
    assert registry.describe("novel_component").lifecycle == "approved"
    assert registered.config_schema["properties"]["value"]["default"] == 1


def _component_request(**changes: object) -> ComponentRequest:
    values: dict[str, object] = {
        "request_id": "component-request-1",
        "project_id": "component-project",
        "component": ComponentSpec(
            component_id="project_novel_component",
            name="Project novel component",
            version="0.1",
            lifecycle="draft",
            outputs=[{"name": "result", "artifact_type": "json"}],
        ),
        "source_ref": "projects/component-project/novel.py",
        "source_hash": "sha256:abc123",
        "dependencies": ["numpy"],
        "test_refs": ["tests/test_project_novel.py"],
        "expected_resource_use": {"cpu_hours": 1, "memory_gb": 2},
    }
    values.update(changes)
    return ComponentRequest(**values)


def _review_context(**changes: object) -> ComponentReviewContext:
    values: dict[str, object] = {
        "source_hash_verified": True,
        "tests_passed": True,
        "config_schema_strict": True,
        "static_handler_binding": True,
        "isolation_enforced": True,
        "approved_dependencies": frozenset({"numpy"}),
        "resource_envelope": {"cpu_hours": 2, "memory_gb": 4},
    }
    values.update(changes)
    if isinstance(values["resource_envelope"], dict):
        from services.contracts.models import BudgetEstimate

        values["resource_envelope"] = BudgetEstimate(**values["resource_envelope"])
    return ComponentReviewContext(**values)


def test_safe_project_component_is_approved_without_human_input() -> None:
    class NovelConfig(BaseModel):
        value: int = 1

    source = Path(__file__).resolve()
    request = _component_request(
        source_ref=str(source), source_hash=f"sha256:{sha256(source.read_bytes()).hexdigest()}"
    )
    review = ComponentReviewService().evaluate(request, context=_review_context())
    assert review.allowed
    assert review.decision == "auto_approve_project_experimental"

    registry = ComponentRegistry(
        allow_experimental=True, experimental_project_id=request.project_id
    )
    ComponentReviewService.approve_and_register(
        request, review, registry, NovelConfig, lambda _: {"result": "unused"}
    )
    assert registry.describe(request.component.component_id).lifecycle == "experimental"


def test_stability_gap_routes_to_revision_without_human_escalation() -> None:
    review = ComponentReviewService().evaluate(
        _component_request(), context=_review_context(tests_passed=False)
    )

    assert not review.allowed
    assert review.decision == "request_revision"
    assert review.required_revisions == ["tests_passed"]


@pytest.mark.parametrize(
    "change, blocker",
    [
        ({"requires_network": True}, "network_denied"),
        ({"requires_subprocess": True}, "subprocess_denied"),
        ({"requires_secrets": True}, "secrets_denied"),
        ({"mutates_shared_state": True}, "shared_state_immutable"),
    ],
)
def test_security_risk_escalates_to_human(change: dict[str, object], blocker: str) -> None:
    review = ComponentReviewService().evaluate(
        _component_request(**change), context=_review_context()
    )

    assert not review.allowed
    assert review.decision == "escalate_for_human_review"
    assert blocker in review.blocked_by


def test_shared_toolbox_request_still_uses_governed_promotion() -> None:
    review = ComponentReviewService().evaluate(
        _component_request(requested_scope="shared_toolbox"), context=_review_context()
    )

    assert not review.allowed
    assert review.blocked_by == ["shared_toolbox_promotion"]


def test_experimental_registry_must_be_project_scoped() -> None:
    with pytest.raises(ValueError, match="scoped to one project"):
        ComponentRegistry(allow_experimental=True)


def test_component_approval_is_bound_to_exact_source_hash() -> None:
    class NovelConfig(BaseModel):
        value: int = 1

    request = _component_request()
    review = ComponentReviewService().evaluate(request, context=_review_context())
    changed = request.model_copy(update={"source_hash": "sha256:different"})
    registry = ComponentRegistry(
        allow_experimental=True, experimental_project_id=request.project_id
    )

    with pytest.raises(PermissionError, match="component source"):
        ComponentReviewService.approve_and_register(
            changed, review, registry, NovelConfig, lambda _: {"result": "unused"}
        )


def test_protected_component_runner_enforces_binding_paths_network_and_subprocess(
    tmp_path: Path,
) -> None:
    import socket
    import subprocess

    class ProtectedConfig(BaseModel):
        mode: str

    source = tmp_path / "component_source.py"
    source.write_text("# immutable component source\n", encoding="utf-8")
    input_file = tmp_path / "inputs" / "source.txt"
    input_file.parent.mkdir()
    input_file.write_text("trusted", encoding="utf-8")
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    spec = ComponentSpec(
        component_id="protected_component",
        name="Protected",
        version="1",
        lifecycle="experimental",
        inputs=[{"name": "source", "artifact_type": "text"}],
        outputs=[{"name": "result", "artifact_type": "text"}],
        supported_execution_backends=["local"],
    )
    registry = ComponentRegistry(
        allow_experimental=True, experimental_project_id="component-project"
    )

    def handler(context):
        if context.config.mode == "network":
            socket.getaddrinfo("example.com", 443)
        if context.config.mode == "subprocess":
            subprocess.run(["true"], check=True)
        target = context.workdir / "result.txt"
        target.write_text(context.inputs["source"].read_text(), encoding="utf-8")
        return {"outputs": {"result": target}}

    handler.__code__ = handler.__code__.replace(co_filename=str(source))
    registry.register(
        spec,
        ProtectedConfig,
        handler,
        source_hash=f"sha256:{sha256(source.read_bytes()).hexdigest()}",
    )
    experiment = ExperimentSpec(
        experiment_spec_id="protected-test",
        project_id="component-project",
        dataset_version_id="v1",
        hypothesis="containment",
        modality="",
        problem_type="",
        execution_backend="local",
        component_graph=[
            {
                "node_id": "node",
                "component_id": "protected_component",
                "component_version": "1",
                "config": {"mode": "ok"},
                "inputs": {"source": str(input_file)},
            }
        ],
    )
    resolved = ExperimentSpecResolver(registry).resolve(experiment)
    plan = compile_component_plan(
        resolved,
        reason_for_experiment="test",
        expected_signal="contained",
        success_criteria="output",
        failure_criteria="violation",
    )
    policy = ProtectedComponentExecution(
        profile=IsolationProfile(
            profile_id="protected-test",
            allowed_read_paths=(str(input_file.parent), str(output_root), str(source)),
            allowed_write_paths=(str(output_root),),
        ),
        source_hashes={"protected_component": f"sha256:{sha256(source.read_bytes()).hexdigest()}"},
        max_cpu_seconds=10,
        max_wall_seconds=10,
        max_memory_bytes=512 * 1024 * 1024,
    )
    result = ComponentGraphRunner(registry).run(
        resolved,
        plan=plan,
        decision=_decision(plan.experiment_plan_id),
        workdir=output_root / "ok",
        protected_execution=policy,
    )
    if __import__("sys").platform == "darwin":
        assert result.tool_runs[0].status == "failed"
        assert "memory enforcement is unavailable on Darwin" in result.tool_runs[0].errors[0]
        return
    assert result.tool_runs[0].status == "succeeded", result.tool_runs[0].errors

    for mode, expected in (("network", "network access"), ("subprocess", "subprocess access")):
        violating = experiment.model_copy(
            update={
                "component_graph": [
                    experiment.component_graph[0].model_copy(update={"config": {"mode": mode}})
                ]
            }
        )
        resolved = ExperimentSpecResolver(registry).resolve(violating)
        plan = compile_component_plan(
            resolved,
            reason_for_experiment="test",
            expected_signal="contained",
            success_criteria="output",
            failure_criteria="violation",
        )
        result = ComponentGraphRunner(registry).run(
            resolved,
            plan=plan,
            decision=_decision(plan.experiment_plan_id),
            workdir=output_root / mode,
            protected_execution=policy,
        )
        assert result.tool_runs[0].status == "failed"
        assert expected in result.tool_runs[0].errors[0]


def test_protected_component_runner_rejects_changed_source(tmp_path: Path) -> None:
    # Hash binding is checked before handler execution, even for trusted registries.
    source = tmp_path / "source.py"
    source.write_text("# source\n", encoding="utf-8")
    policy = ProtectedComponentExecution(
        profile=IsolationProfile(
            profile_id="p",
            allowed_read_paths=(str(tmp_path),),
            allowed_write_paths=(str(tmp_path),),
        ),
        source_hashes={"component": "sha256:incorrect"},
        max_cpu_seconds=1,
        max_wall_seconds=1,
        max_memory_bytes=64 * 1024 * 1024,
    )
    with pytest.raises(Exception, match="source hash"):
        from services.components.registry import RegisteredComponent

        ComponentGraphRunner._validate_protected_binding(
            RegisteredComponent(
                ComponentSpec(component_id="component", name="component", version="1"),
                BaseModel,
                lambda _: None,
            ),
            policy,
        )
