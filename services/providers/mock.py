"""Deterministic scientist provider used by conformance and workflow tests."""

from enum import StrEnum
from typing import Any

from services.contracts import DiagnosticPacket, ProviderProfile
from services.contracts.models import BudgetEstimate

from .artifacts import ArtifactSink, MemoryArtifactSink
from .errors import ProviderCallError
from .normalization import normalize_review
from .privacy import filter_diagnostic_packet, is_raw_response_reference


class MockResponseMode(StrEnum):
    VALID = "valid"
    INVALID_ACTION_TYPE = "invalid_action_type"
    MALFORMED_RESPONSE = "malformed_response"
    LOW_CONFIDENCE = "low_confidence"
    STOP_RECOMMENDATION = "stop_recommendation"
    HUMAN_REVIEW_RECOMMENDATION = "human_review_recommendation"
    DATASET_CHANGE_RECOMMENDATION = "dataset_change_recommendation"
    FAILURE = "failure"


class MockScientistProvider:
    """A recommendation-only provider; it has no tool, decision, or persistence access."""

    def __init__(
        self,
        profile: ProviderProfile,
        *,
        mode: MockResponseMode = MockResponseMode.VALID,
        artifact_sink: ArtifactSink | None = None,
    ) -> None:
        if profile.provider_type != "mock_provider":
            raise ValueError("MockScientistProvider requires a mock_provider profile")
        self.profile = profile
        self.mode = mode
        self.artifact_sink = artifact_sink or MemoryArtifactSink()

    def review(
        self,
        packet: DiagnosticPacket,
        *,
        experiment_ids: list[str] | None = None,
        prompt_template_version: str = "1.0",
    ) -> Any:
        filtered = filter_diagnostic_packet(packet, self.profile)
        if self.mode == MockResponseMode.FAILURE:
            raise ProviderCallError("deterministic mock provider failure")
        raw = self._response(filtered, experiment_ids or [])
        artifact = self.artifact_sink.capture_raw_response(
            raw,
            provider_id=self.profile.provider_id,
            metadata={
                "diagnostic_packet_id": packet.diagnostic_packet_id,
                "prompt_template_version": prompt_template_version,
            },
        )
        return normalize_review(
            raw,
            packet=filtered,
            provider_profile_id=self.profile.provider_id,
            model_name=self.profile.model_name,
            prompt_template_version=prompt_template_version,
            raw_response_artifact=artifact,
        )

    def _response(self, packet: DiagnosticPacket, experiment_ids: list[str]) -> dict[str, Any]:
        action = "run_error_analysis"
        if self.mode == MockResponseMode.INVALID_ACTION_TYPE:
            action = "execute_tools_directly"
        elif self.mode == MockResponseMode.STOP_RECOMMENDATION:
            action = "stop_low_expected_value"
        elif self.mode == MockResponseMode.HUMAN_REVIEW_RECOMMENDATION:
            action = "create_human_review_queue"
        elif self.mode == MockResponseMode.DATASET_CHANGE_RECOMMENDATION:
            action = "create_dataset_improvement_proposal"
        if self.mode == MockResponseMode.MALFORMED_RESPONSE:
            return {"review_id": "malformed"}
        confidence = 0.2 if self.mode == MockResponseMode.LOW_CONFIDENCE else 0.8
        return {
            "review_id": f"mock-review-{packet.diagnostic_packet_id}-{self.mode.value}",
            "project_id": packet.project_id,
            "experiment_ids": experiment_ids,
            "provider_profile_id": self.profile.provider_id,
            "model_name": self.profile.model_name,
            "prompt_template_version": "1.0",
            "diagnostic_packet_id": packet.diagnostic_packet_id,
            "primary_diagnosis": "insufficient_benchmark_quality",
            "diagnosis_confidence": confidence,
            "supporting_evidence": ["diagnostic_packet.dataset_characterization_summary"],
            "counter_evidence": ["evidence is bounded by the supplied packet"],
            "recommended_next_action": action,
            "expected_value": "medium",
            "estimated_cost": BudgetEstimate(cpu_hours=1),
            "stop_recommendation": (
                "low_expected_value" if self.mode == MockResponseMode.STOP_RECOMMENDATION else None
            ),
            "escalation_required": self.mode
            in {
                MockResponseMode.HUMAN_REVIEW_RECOMMENDATION,
                MockResponseMode.DATASET_CHANGE_RECOMMENDATION,
            },
            "human_review_required": self.mode
            in {
                MockResponseMode.HUMAN_REVIEW_RECOMMENDATION,
                MockResponseMode.DATASET_CHANGE_RECOMMENDATION,
            },
            "knowledge_references": packet.knowledge_context_refs,
            "evidence_references": [
                ref for ref in packet.artifact_refs if not is_raw_response_reference(ref)
            ],
            "uncertainty_notes": ["Mock response; not an authorization decision."],
        }
