"""Assembly of structured diagnostic packets from experiment evidence."""

from collections.abc import Iterable
from typing import Any

from services.contracts import DiagnosticPacket, EvaluationPolicy, ToolRunResult
from services.contracts.models import PrivacyMode


def assemble_diagnostic_packet(
    *,
    diagnostic_packet_id: str,
    project_id: str,
    problem_type: str,
    dataset_version_id: str,
    privacy_mode: PrivacyMode | str,
    dataset_characterization_summary: str | None = None,
    evaluation_policy: EvaluationPolicy | None = None,
    tool_results: Iterable[ToolRunResult] = (),
    model_comparison: list[dict[str, Any]] | None = None,
    learning_curve_summary: dict[str, Any] | None = None,
    error_analysis_summary: dict[str, Any] | None = None,
    cluster_analysis_summary: dict[str, Any] | None = None,
    calibration_summary: dict[str, Any] | None = None,
    current_project_state: str | None = None,
    budget_remaining: Any = None,
    allowed_recommendation_types: list[str] | None = None,
    open_questions: list[str] | None = None,
    knowledge_context_refs: list[str] | None = None,
    system_context_refs: list[str] | None = None,
    project_context_refs: list[str] | None = None,
    agent_context: dict[str, Any] | None = None,
    artifact_refs: list[str] | None = None,
) -> DiagnosticPacket:
    """Build a packet while retaining structured run history and artifact provenance."""

    results = list(tool_results)
    history = [result.experiment_plan_id or result.tool_run_id for result in results]
    run_artifacts = [artifact for result in results for artifact in result.artifact_refs]
    return DiagnosticPacket(
        diagnostic_packet_id=diagnostic_packet_id,
        project_id=project_id,
        problem_type=problem_type,
        dataset_version_id=dataset_version_id,
        dataset_characterization_summary=dataset_characterization_summary,
        evaluation_policy=evaluation_policy,
        model_comparison=list(model_comparison or []),
        learning_curve_summary=learning_curve_summary,
        error_analysis_summary=error_analysis_summary,
        cluster_analysis_summary=cluster_analysis_summary,
        calibration_summary=calibration_summary,
        experiment_history=history,
        current_project_state=current_project_state,
        budget_remaining=budget_remaining,
        allowed_recommendation_types=list(allowed_recommendation_types or []),
        privacy_mode=PrivacyMode(privacy_mode),
        open_questions=list(open_questions or []),
        knowledge_context_refs=list(knowledge_context_refs or []),
        system_context_refs=list(system_context_refs or []),
        project_context_refs=list(project_context_refs or []),
        agent_context=dict(agent_context or {}),
        artifact_refs=list(dict.fromkeys([*run_artifacts, *(artifact_refs or [])])),
    )
