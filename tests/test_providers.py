"""Focused scientist-provider boundary tests."""

import pytest
from services.contracts import DiagnosticPacket, ProviderProfile
from services.contracts.models import PrivacyMode
from services.providers import (
    MemoryArtifactSink,
    MockResponseMode,
    MockScientistProvider,
    ProviderPrivacyError,
    ProviderValidationError,
    load_provider_profile,
    normalize_review,
)


def packet(mode: PrivacyMode = PrivacyMode.SUMMARY_ONLY) -> DiagnosticPacket:
    return DiagnosticPacket(
        diagnostic_packet_id="packet-1",
        project_id="project-1",
        problem_type="classification",
        dataset_version_id="dataset-1",
        dataset_characterization_summary="summary",
        privacy_mode=mode,
        allowed_recommendation_types=["run_error_analysis"],
        artifact_refs=["artifact://plot/1"],
        knowledge_context_refs=["knowledge://fact/1"],
        system_context_refs=["policies/evidence.md"],
        project_context_refs=["10_context/current_state.md"],
        agent_context={"assignment": "review"},
    )


def profile(**kwargs: object) -> ProviderProfile:
    values: dict[str, object] = {
        "provider_id": "mock",
        "provider_type": "mock_provider",
        "model_name": "deterministic",
        "privacy_capabilities": [PrivacyMode.SUMMARY_ONLY, PrivacyMode.KNOWLEDGE],
    }
    values.update(kwargs)
    return ProviderProfile(**values)


def test_mock_is_deterministic_and_captures_raw_response() -> None:
    sink = MemoryArtifactSink()
    review = MockScientistProvider(profile(), artifact_sink=sink).review(packet())
    assert review.review_id == "mock-review-packet-1-valid"
    assert review.raw_response_artifact in sink.responses
    assert review.recommended_next_action == "run_error_analysis"


@pytest.mark.parametrize("mode", list(MockResponseMode)[1:])
def test_required_mock_modes_are_structured(mode: MockResponseMode) -> None:
    allowed = [
        "run_error_analysis",
        "stop_low_expected_value",
        "create_human_review_queue",
        "create_dataset_improvement_proposal",
    ]
    current = packet()
    current = current.model_copy(update={"allowed_recommendation_types": allowed})
    provider = MockScientistProvider(profile(), mode=mode, artifact_sink=MemoryArtifactSink())
    if mode in {MockResponseMode.FAILURE}:
        with pytest.raises(Exception, match="deterministic mock provider failure"):
            provider.review(current)
    elif mode in {MockResponseMode.INVALID_ACTION_TYPE, MockResponseMode.MALFORMED_RESPONSE}:
        with pytest.raises(ProviderValidationError):
            provider.review(current)
    else:
        assert provider.review(current).review_id.endswith(mode.value)


def test_privacy_filter_removes_artifacts_and_knowledge() -> None:
    filtered = MockScientistProvider(profile(), artifact_sink=MemoryArtifactSink()).review(packet())
    assert filtered.evidence_references == []
    assert filtered.knowledge_references == []


def test_external_provider_is_blocked_by_local_only() -> None:
    external = profile(provider_type="openai")
    with pytest.raises(ProviderPrivacyError):
        from services.providers import filter_diagnostic_packet

        filter_diagnostic_packet(packet(PrivacyMode.LOCAL_ONLY), external)


def test_profile_loader_validates_mapping() -> None:
    loaded = load_provider_profile(
        {"provider_id": "mock", "provider_type": "mock_provider", "model_name": "m"}
    )
    assert loaded.provider_id == "mock"


def test_privacy_filter_redacts_nested_secrets_and_raw_response_refs() -> None:
    current = packet(PrivacyMode.PLOTS).model_copy(
        update={
            "model_comparison": [{"nested": {"api_key": "sk-live-secret", "safe": "measurement"}}],
            "artifact_refs": [
                "artifact://scientist-response/mock/abc",
                "artifact://plot/allowed",
            ],
            "knowledge_context_refs": ["artifact://raw-response/provider/abc"],
        }
    )
    from services.providers import filter_diagnostic_packet

    filtered = filter_diagnostic_packet(current, profile(privacy_capabilities=[PrivacyMode.PLOTS]))
    assert filtered.model_comparison == [
        {"nested": {"api_key": "[REDACTED]", "safe": "measurement"}}
    ]
    assert filtered.artifact_refs == ["artifact://plot/allowed"]
    assert filtered.knowledge_context_refs == []
    assert filtered.system_context_refs == []
    assert filtered.project_context_refs == []
    assert filtered.agent_context == {}


def test_raw_response_capture_is_sanitized() -> None:
    sink = MemoryArtifactSink()
    sink.capture_raw_response(
        {"nested": {"password": "do-not-store", "result": "ok"}},
        provider_id="mock",
        metadata={"token": "also-do-not-store"},
    )
    stored = next(iter(sink.responses.values()))
    assert stored["response"] == {"nested": {"password": "[REDACTED]", "result": "ok"}}
    assert stored["metadata"] == {"token": "[REDACTED]"}


def test_normalized_review_does_not_share_raw_response_references() -> None:
    current = packet().model_copy(update={"artifact_refs": ["artifact://plot/1"]})
    provider = MockScientistProvider(profile(), artifact_sink=MemoryArtifactSink())
    review = provider.review(current)
    assert all("scientist-response" not in ref for ref in review.evidence_references)


def test_normalization_preserves_an_authoritative_provider_usage_receipt() -> None:
    current = packet()
    provider = MockScientistProvider(profile(), artifact_sink=MemoryArtifactSink())
    raw = provider._response(current, [])
    raw["provider_token_usage"] = {
        "reporting_source": "provider.response.usage",
        "total_tokens": 42,
        "input_tokens": 30,
        "output_tokens": 12,
        "billed_cost_usd": 0.0042,
        "source_reference": "artifact://provider-response/packet-1",
    }

    review = normalize_review(
        raw,
        packet=current,
        provider_profile_id="mock",
        model_name="deterministic",
        prompt_template_version="1.0",
        raw_response_artifact="artifact://provider-response/packet-1",
    )

    assert review.provider_token_usage is not None
    assert review.provider_token_usage.total_tokens == 42
    assert review.provider_token_usage.billed_cost_usd == pytest.approx(0.0042)
