"""Append-only, receipt-based token telemetry for LASI actions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from services.contracts import (
    ActionTokenUsage,
    ProviderTokenUsage,
    TokenUsageBreakdown,
    TokenUsageReport,
    TokenUsageStatus,
)
from services.memory import ActionUsage, OperationalMemory


@dataclass(frozen=True, slots=True)
class ProjectTokenUsageSummary:
    """Measured project usage, with coverage made explicit instead of guessed."""

    project_id: str | None
    action_count: int
    reported_action_count: int
    unavailable_action_count: int
    not_applicable_action_count: int
    total_tokens: int
    billed_cost_usd: float
    by_action_type: dict[str, int]


class TokenUsageService:
    """Persist actual usage receipts and expose transparent efficiency summaries."""

    def __init__(self, memory: OperationalMemory) -> None:
        self._memory = memory

    def record(self, usage: ActionTokenUsage) -> ActionUsage:
        """Append a metering record; existing entries may not be overwritten."""
        if self._memory.get(ActionUsage, usage.action_usage_id) is not None:
            raise ValueError(f"action usage already exists: {usage.action_usage_id}")
        receipt = usage.usage
        record = ActionUsage(
            action_usage_id=usage.action_usage_id,
            project_id=usage.project_id,
            action_id=usage.action_id,
            action_type=usage.action_type,
            metering_status=usage.status,
            provider_profile_id=usage.provider_profile_id,
            model_name=usage.model_name,
            reporting_source=receipt.reporting_source if receipt else None,
            source_reference=receipt.source_reference if receipt else None,
            input_tokens=receipt.input_tokens if receipt else None,
            output_tokens=receipt.output_tokens if receipt else None,
            cached_input_tokens=receipt.cached_input_tokens if receipt else None,
            total_tokens=receipt.total_tokens if receipt else None,
            billed_cost_usd=receipt.billed_cost_usd if receipt else None,
            unavailable_reason=usage.unavailable_reason,
            reported_at=receipt.reported_at if receipt else None,
            created_at=usage.created_at or datetime.now(UTC),
            payload=usage.model_dump(mode="json"),
        )
        return self._memory.add(record)

    def record_provider_action(
        self,
        *,
        project_id: str,
        action_id: str,
        action_type: str,
        provider_profile_id: str,
        model_name: str,
        usage: ProviderTokenUsage | None,
    ) -> ActionUsage:
        """Record a provider action from its receipt, or explicitly record the gap."""
        return self.record(
            ActionTokenUsage(
                action_usage_id=f"usage-{action_id}",
                project_id=project_id,
                action_id=action_id,
                action_type=action_type,
                status=TokenUsageStatus.REPORTED if usage else TokenUsageStatus.NOT_AVAILABLE,
                provider_profile_id=provider_profile_id,
                model_name=model_name,
                usage=usage,
                unavailable_reason=(
                    None
                    if usage
                    else "provider or agent runtime did not return an authoritative usage receipt"
                ),
            )
        )

    def record_not_applicable(
        self, *, project_id: str, action_id: str, action_type: str, reason: str
    ) -> ActionUsage:
        """Record a non-LLM action explicitly so zero is not confused with missing data."""
        return self.record(
            ActionTokenUsage(
                action_usage_id=f"usage-{action_id}",
                project_id=project_id,
                action_id=action_id,
                action_type=action_type,
                status=TokenUsageStatus.NOT_APPLICABLE,
                unavailable_reason=reason,
            )
        )

    def project_summary(self, project_id: str) -> ProjectTokenUsageSummary:
        return self._summarize(self._memory.list_for_project(ActionUsage, project_id), project_id)

    def portfolio_summary(self) -> ProjectTokenUsageSummary:
        return self._summarize(self._memory.list_all(ActionUsage), None)

    def action_records(self, project_id: str) -> list[ActionUsage]:
        """Return the project's append-only records for a readable projection."""
        return cast(list[ActionUsage], self._memory.list_for_project(ActionUsage, project_id))

    def project_report(self, project_id: str) -> TokenUsageReport:
        """Return exact input/output totals and descending action-type breakdown."""
        records = self.action_records(project_id)
        groups: dict[str, list[ActionUsage]] = defaultdict(list)
        for record in records:
            groups[record.action_type].append(record)

        def total(items: Iterable[ActionUsage], field: str) -> int | float:
            return sum(getattr(item, field) or 0 for item in items)

        breakdown = [
            TokenUsageBreakdown(
                action_type=action_type,
                action_count=len(items),
                reported_action_count=sum(
                    item.metering_status == TokenUsageStatus.REPORTED for item in items
                ),
                unavailable_action_count=sum(
                    item.metering_status == TokenUsageStatus.NOT_AVAILABLE for item in items
                ),
                not_applicable_action_count=sum(
                    item.metering_status == TokenUsageStatus.NOT_APPLICABLE for item in items
                ),
                input_tokens=int(total(items, "input_tokens")),
                output_tokens=int(total(items, "output_tokens")),
                cached_input_tokens=int(total(items, "cached_input_tokens")),
                total_tokens=int(total(items, "total_tokens")),
                billed_cost_usd=float(total(items, "billed_cost_usd")),
            )
            for action_type, items in groups.items()
        ]
        breakdown.sort(key=lambda item: (-item.total_tokens, item.action_type))
        summary = self.project_summary(project_id)
        return TokenUsageReport(
            action_count=summary.action_count,
            reported_action_count=summary.reported_action_count,
            unavailable_action_count=summary.unavailable_action_count,
            not_applicable_action_count=summary.not_applicable_action_count,
            input_tokens=int(total(records, "input_tokens")),
            output_tokens=int(total(records, "output_tokens")),
            cached_input_tokens=int(total(records, "cached_input_tokens")),
            total_tokens=summary.total_tokens,
            billed_cost_usd=summary.billed_cost_usd,
            breakdown=breakdown,
        )

    @staticmethod
    def _summarize(
        records: Iterable[ActionUsage], project_id: str | None
    ) -> ProjectTokenUsageSummary:
        items = list(records)
        by_action_type: dict[str, int] = defaultdict(int)
        for item in items:
            by_action_type[item.action_type] += 1
        return ProjectTokenUsageSummary(
            project_id=project_id,
            action_count=len(items),
            reported_action_count=sum(
                item.metering_status == TokenUsageStatus.REPORTED for item in items
            ),
            unavailable_action_count=sum(
                item.metering_status == TokenUsageStatus.NOT_AVAILABLE for item in items
            ),
            not_applicable_action_count=sum(
                item.metering_status == TokenUsageStatus.NOT_APPLICABLE for item in items
            ),
            total_tokens=sum(item.total_tokens or 0 for item in items),
            billed_cost_usd=sum(item.billed_cost_usd or 0.0 for item in items),
            by_action_type=dict(sorted(by_action_type.items())),
        )
