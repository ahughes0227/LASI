from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from services.contracts import ActionTokenUsage, ProviderTokenUsage, TokenUsageStatus
from services.memory import Base, OperationalMemory, Project, create_engine, create_session_factory
from services.telemetry import TokenUsageService


def _service() -> TokenUsageService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    memory.add(
        Project(project_id="p", project_name="Telemetry", problem_type="test", modality="tabular")
    )
    return TokenUsageService(memory)


def test_token_usage_ledger_preserves_provider_reported_values_and_summarizes() -> None:
    service = _service()
    service.record_provider_action(
        project_id="p",
        action_id="review-1",
        action_type="scientist_review",
        provider_profile_id="openai-reviewer",
        model_name="test-model",
        usage=ProviderTokenUsage(
            reporting_source="provider.response.usage",
            total_tokens=125,
            input_tokens=100,
            output_tokens=25,
            billed_cost_usd=0.0125,
            reported_at=datetime.now(UTC),
            source_reference="artifact://provider-response/review-1",
        ),
    )
    service.record_not_applicable(
        project_id="p",
        action_id="report-1",
        action_type="report_generation",
        reason="fixed template",
    )

    summary = service.project_summary("p")

    assert summary.total_tokens == 125
    assert summary.billed_cost_usd == pytest.approx(0.0125)
    assert summary.reported_action_count == 1
    assert summary.not_applicable_action_count == 1
    assert summary.unavailable_action_count == 0
    assert summary.by_action_type == {"report_generation": 1, "scientist_review": 1}
    report = service.project_report("p")
    assert report.input_tokens == 100
    assert report.output_tokens == 25
    assert report.breakdown[0].action_type == "scientist_review"
    assert report.breakdown[0].total_tokens == 125


def test_missing_or_estimated_usage_is_explicitly_rejected_or_marked_unavailable() -> None:
    with pytest.raises(ValidationError, match="estimated token usage"):
        ProviderTokenUsage(reporting_source="estimated by llm", total_tokens=3)
    with pytest.raises(ValidationError, match="requires an authoritative usage receipt"):
        ActionTokenUsage(
            action_usage_id="usage-1",
            project_id="p",
            action_id="review-1",
            action_type="scientist_review",
            status=TokenUsageStatus.REPORTED,
        )

    service = _service()
    record = service.record_provider_action(
        project_id="p",
        action_id="review-without-receipt",
        action_type="scientist_review",
        provider_profile_id="mock",
        model_name="deterministic",
        usage=None,
    )

    assert record.metering_status == "not_available"
    assert record.total_tokens is None
    assert service.project_summary("p").total_tokens == 0
