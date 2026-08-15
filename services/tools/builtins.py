"""Deterministic built-in tool registrations."""

# fmt: off

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from services.contracts import ApprovalRecord, DatasetManifest, ToolSpec

from .adapters import characterize_dataset, validate_dataset
from .error_analysis import run_error_analysis
from .registry import ToolRegistry
from .runner import ToolContext, ToolOutput

_DIRECT_GBDT_APPROVAL = (
    Path(__file__).resolve().parents[2]
    / "projects/mercury/40_output/approvals/APP-MERCURY-DIRECT-GBDT-COMPONENT-0001.yaml"
)
_DIRECT_GBDT_APPROVAL_SHA256 = "56067955d5a174fcc338eab15a6e10409b06b458d43e28d3c4167892ca324a7b"


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


def _spec(tool_id: str, name: str, description: str, *, modalities: list[str] | None = None,
          problem_types: list[str] | None = None,
          capability_state: str = "production_ready") -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        name=name,
        version="1.0",
        description=description,
        supported_execution_backends=["local"],
        supported_modalities=modalities or [],
        supported_problem_types=problem_types or [],
        capability_state=capability_state,
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
            _spec(
                "error_analysis",
                "Error analysis",
                "Build structured RMSLE error buckets from row-level predictions.",
                modalities=["tabular", "time_series"],
                problem_types=["regression", "forecasting"],
            ),
            run_error_analysis,
        ),
        (
            _spec("clustering", "Clustering analysis", "Analyze embedding clusters."),
            _pass_through("clustering"),
        ),
        (
            _spec("static_report", "Static report", "Register static report generation."),
            _pass_through("static_report"),
        ),
        (
            _spec(
                "component_pipeline",
                "Component pipeline",
                "Run an approved immutable component experiment specification.",
            ),
            _pass_through("component_pipeline"),
        ),
    ]
    for spec, handler in registrations:
        if not any(existing.tool_id == spec.tool_id for existing in registry.all()):
            registry.register(spec, handler)
    return registry


def register_tabular_baseline(registry: ToolRegistry) -> ToolRegistry:
    """Opt-in registration for the real tabular baseline.

    Kept separate so legacy diagnostic tool inventories remain stable while the
    challenge workflow can explicitly allowlist this higher-consequence tool.
    """
    # Keep this dependency behind the explicit registration boundary. Importing
    # the tabular handler also needs ToolContext/ToolOutput from this package.
    from services.tabular import run_tabular_baseline

    spec = _spec(
        "train_tabular_baseline",
        "Deterministic tabular baseline",
        "Run a governed classification or regression baseline.",
        modalities=["tabular"],
        problem_types=["classification", "regression"],
    )
    if not any(existing.tool_id == spec.tool_id for existing in registry.all()):
        registry.register(spec, run_tabular_baseline)
    return registry


def register_seasonal_naive_baseline(
    registry: ToolRegistry, *, approval: ApprovalRecord
) -> ToolRegistry:
    """Opt-in registration for the trusted local time-series reference tool."""
    if (
        approval.approval_id != "APP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001"
        or approval.project_id != "mercury"
        or approval.proposal_id != "PROP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001"
        or approval.action_type != "update_toolbox"
        or approval.approval_status != "approved"
    ):
        raise PermissionError(
            "a matching approved seasonal-naive toolbox authorization is required"
        )
    if approval.expires_at is not None:
        from datetime import UTC, datetime

        if approval.expires_at < datetime.now(UTC):
            raise PermissionError("seasonal-naive toolbox authorization has expired")
    from services.timeseries import run_seasonal_naive_baseline

    spec = _spec(
        "seasonal_naive_baseline",
        "Seasonal-naive time-series baseline",
        "Run a past-only, nonnegative seasonal-naive panel forecast.",
        modalities=["tabular_time_series"],
        problem_types=["forecasting"],
    ).model_copy(
        update={
            "version": "0.1.0",
            "expected_artifacts": ["validation_predictions.csv", "metrics.json"],
            "failure_modes": [
                "invalid_schema",
                "duplicate_panel_key",
                "invalid_chronology",
                "benchmark_isolation_error",
                "missing_artifact",
            ],
        }
    )
    if not any(existing.tool_id == spec.tool_id for existing in registry.all()):
        registry.register(spec, run_seasonal_naive_baseline)
    return registry


def register_direct_horizon_gbdt(
    registry: ToolRegistry, *, approval: ApprovalRecord, approval_path: str | Path | None = None
) -> ToolRegistry:
    """Register the reviewed Mercury divergent direct-horizon component."""
    if approval_path is not None and Path(approval_path).resolve() != _DIRECT_GBDT_APPROVAL:
        raise PermissionError(
            "direct-GBDT approval path is not the authoritative approval artifact"
        )
    approval_bytes = _DIRECT_GBDT_APPROVAL.read_bytes()
    if hashlib.sha256(approval_bytes).hexdigest() != _DIRECT_GBDT_APPROVAL_SHA256:
        raise PermissionError("direct-GBDT approval artifact integrity check failed")
    loaded = yaml.safe_load(approval_bytes)
    if not isinstance(loaded, dict):
        raise PermissionError("direct-GBDT approval artifact must be a mapping")
    durable = ApprovalRecord.model_validate(loaded)
    if durable != approval:
        raise PermissionError("direct-GBDT approval does not match durable artifact")
    required_conditions = {
        "Local-only, deny-all benchmark isolation and explicit path allowlists.",
        "Official local files only; no supplemental sources in this component.",
        "Direct past-only feature construction and same-split validation before submission.",
        "Record tool runs, artifacts, failures, and usage coverage.",
    }
    if not required_conditions.issubset(set(durable.conditions)):
        raise PermissionError("direct-GBDT approval conditions are incomplete")
    if (
        approval.approval_id != "APP-MERCURY-DIRECT-GBDT-COMPONENT-0001"
        or approval.project_id != "mercury"
        or approval.proposal_id != "PROP-MERCURY-DIRECT-GBDT-COMPONENT-0001"
        or approval.action_type != "update_toolbox"
        or approval.approval_status != "approved"
        or (approval.expires_at is not None and approval.expires_at < datetime.now(UTC))
    ):
        raise PermissionError("a matching approved direct-GBDT authorization is required")
    from services.timeseries import run_direct_horizon_gbdt

    spec = _spec(
        "direct_horizon_gbdt",
        "Direct multi-horizon GBDT forecaster",
        "Past-only global direct-horizon retail forecaster.",
        modalities=["tabular_time_series"],
        problem_types=["forecasting"],
    ).model_copy(update={"version": "0.1.0"})
    if not any(existing.tool_id == spec.tool_id for existing in registry.all()):
        registry.register(spec, run_direct_horizon_gbdt)
    return registry
