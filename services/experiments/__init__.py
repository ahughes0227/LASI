"""Deterministic experiment planning and evidence assembly services."""

from .compiler import CompilationResult, ExperimentPlanCompiler, compile_plan
from .component_plan import compile_component_plan
from .diagnostics import assemble_diagnostic_packet
from .duplicates import DuplicateExperimentDetector, DuplicateMatch
from .execution import experiment_plan_content_hash, require_allowed_decision
from .reproducibility import ReproducibilityRecord, build_reproducibility_record

__all__ = [
    "CompilationResult",
    "DuplicateExperimentDetector",
    "DuplicateMatch",
    "ExperimentPlanCompiler",
    "ReproducibilityRecord",
    "assemble_diagnostic_packet",
    "build_reproducibility_record",
    "compile_plan",
    "compile_component_plan",
    "experiment_plan_content_hash",
    "require_allowed_decision",
]
