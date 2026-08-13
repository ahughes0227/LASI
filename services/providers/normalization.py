"""Provider response normalization into the frozen ScientistReview contract."""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from services.contracts import DiagnosticPacket, ScientistReview

from .errors import ProviderValidationError
from .privacy import is_raw_response_reference

KNOWN_ACTIONS = frozenset(
    {
        "run_experiment",
        "run_error_analysis",
        "run_learning_curve",
        "run_embedding_analysis",
        "create_human_review_queue",
        "create_dataset_improvement_proposal",
        "stop_low_expected_value",
        "collect_more_data",
        "revise_label_policy",
        "compare_against_prior_dataset",
        "update_report_only",
    }
)


def normalize_review(
    raw_response: ScientistReview | Mapping[str, Any],
    *,
    packet: DiagnosticPacket,
    provider_profile_id: str,
    model_name: str,
    prompt_template_version: str,
    raw_response_artifact: str,
) -> ScientistReview:
    """Validate native output and attach provider-owned traceability fields."""
    if isinstance(raw_response, ScientistReview):
        values = raw_response.model_dump(mode="python")
    elif isinstance(raw_response, Mapping):
        values = dict(raw_response)
    else:
        raise ProviderValidationError(
            "provider response must be a ScientistReview or mapping", error_type="invalid_response"
        )
    values.update(
        {
            "project_id": packet.project_id,
            "provider_profile_id": provider_profile_id,
            "model_name": model_name,
            "prompt_template_version": prompt_template_version,
            "diagnostic_packet_id": packet.diagnostic_packet_id,
            "raw_response_artifact": raw_response_artifact,
        }
    )
    for field in ("knowledge_references", "evidence_references"):
        if field in values:
            values[field] = [
                reference
                for reference in values[field]
                if isinstance(reference, str) and not is_raw_response_reference(reference)
            ]
    try:
        review = ScientistReview.model_validate(values)
    except ValidationError as exc:
        raise ProviderValidationError(str(exc)) from exc
    if review.recommended_next_action not in KNOWN_ACTIONS:
        raise ProviderValidationError(
            f"unsupported recommendation type: {review.recommended_next_action}",
            error_type="invalid_action_type",
        )
    if (
        packet.allowed_recommendation_types
        and review.recommended_next_action not in packet.allowed_recommendation_types
    ):
        raise ProviderValidationError(
            f"recommendation type is not allowed by packet: {review.recommended_next_action}",
            error_type="invalid_action_type",
        )
    return review
