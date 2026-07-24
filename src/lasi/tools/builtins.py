"""Deterministic MVP tool registrations."""

from collections.abc import Callable

from lasi.contracts import DatasetManifest, ToolSpec

from .adapters import characterize_dataset, validate_dataset
from .registry import ToolRegistry
from .runner import ToolContext, ToolOutput


def _dataset_validation(context: ToolContext) -> ToolOutput:
    manifest = context.parameters.get("manifest")
    if not isinstance(manifest, DatasetManifest):
        raise ValueError("parameters.manifest must be a DatasetManifest")
    errors = validate_dataset(manifest, context.parameters.get("base_path"))
    return ToolOutput(
        metrics={"error_count": len(errors), "valid": not errors},
        errors=errors,
        partial_success=(
            {
                "what_succeeded": ["manifest checks"],
                "what_failed": errors,
                "missing_artifacts": [],
                "diagnostic_impact": "validation",
                "can_continue": False,
            }
            if errors
            else None
        ),
    )


def _characterization(context: ToolContext) -> ToolOutput:
    manifest = context.parameters.get("manifest")
    if not isinstance(manifest, DatasetManifest):
        raise ValueError("parameters.manifest must be a DatasetManifest")
    profile = characterize_dataset(manifest)
    return ToolOutput(
        metrics={"sample_size": profile.sample_size, "class_count": len(profile.class_balance)},
        output_refs=[f"characterization:{profile.characterization_id}"],
    )


def _pass_through(name: str) -> Callable[[ToolContext], ToolOutput]:
    def handler(context: ToolContext) -> ToolOutput:
        return ToolOutput(output_refs=[f"{name}:{context.tool_run_id}"])

    return handler


def _spec(tool_id: str, name: str, description: str) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        name=name,
        version="1.0",
        description=description,
        supported_execution_backends=["local"],
    )


def register_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    registrations: list[tuple[ToolSpec, Callable[[ToolContext], ToolOutput]]] = [
        (
            _spec(
                "dataset_validation", "Dataset validation", "Validate a canonical dataset manifest."
            ),
            _dataset_validation,
        ),
        (
            _spec(
                "dataset_characterization",
                "Dataset characterization",
                "Profile a canonical dataset manifest.",
            ),
            _characterization,
        ),
        (
            _spec("baseline", "Baseline probe", "Run a bounded baseline probe."),
            _pass_through("baseline"),
        ),
        (
            _spec("learning_curve", "Learning curve", "Compute a learning curve."),
            _pass_through("learning_curve"),
        ),
        (
            _spec("error_analysis", "Error analysis", "Build structured error buckets."),
            _pass_through("error_analysis"),
        ),
        (
            _spec("clustering", "Clustering analysis", "Analyze embedding clusters."),
            _pass_through("clustering"),
        ),
        (
            _spec("static_report", "Static report", "Register static report generation."),
            _pass_through("static_report"),
        ),
    ]
    for spec, handler in registrations:
        if not any(existing.tool_id == spec.tool_id for existing in registry.all()):
            registry.register(spec, handler)
    return registry
