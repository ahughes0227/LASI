"""Compile a resolved component graph into the existing governed plan contract."""

from services.components.specs import ResolvedExperimentSpec
from services.contracts import ExperimentPlan
from services.contracts.models import PlannedToolRun, Provenance


def compile_component_plan(
    resolved: ResolvedExperimentSpec,
    *,
    reason_for_experiment: str,
    expected_signal: str,
    success_criteria: str,
    failure_criteria: str,
    created_by: str | None = None,
) -> ExperimentPlan:
    """Create the single authorization target for an immutable component graph."""
    return ExperimentPlan(
        experiment_plan_id=f"plan-{resolved.spec.experiment_spec_id}",
        project_id=resolved.spec.project_id,
        dataset_version=resolved.spec.dataset_version_id,
        hypothesis=resolved.spec.hypothesis,
        reason_for_experiment=reason_for_experiment,
        experiment_type="component_pipeline",
        planned_tool_runs=[
            PlannedToolRun(
                tool_id="component_pipeline",
                run_id=f"run-{resolved.spec.experiment_spec_id}",
                inputs=[resolved.spec.dataset_version_id],
                parameters={
                    "resolved_spec_hash": resolved.content_hash,
                    "component_ids": [
                        node["component_id"] for node in resolved.resolved["component_graph"]
                    ],
                },
            )
        ],
        execution_backend=resolved.spec.execution_backend,
        expected_artifacts=["resolved-experiment-spec.json", *resolved.spec.expected_outputs],
        expected_signal=expected_signal,
        success_criteria=success_criteria,
        failure_criteria=failure_criteria,
        created_by=created_by,
        created_at=resolved.spec.provenance.created_at,
        provenance=Provenance(
            project_id=resolved.spec.project_id,
            dataset_version_id=resolved.spec.dataset_version_id,
            content_hash=resolved.content_hash,
        ),
    )
