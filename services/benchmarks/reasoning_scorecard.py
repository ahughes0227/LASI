"""Comparable scorecards for the frozen Titanic reasoning benchmark."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccuracyMeasurement(_StrictFrozenModel):
    status: Literal["measured", "not_available"]
    value: float | None = Field(default=None, ge=0, le=1)
    source_reference: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> AccuracyMeasurement:
        if self.status == "measured" and (self.value is None or not self.source_reference):
            raise ValueError("measured accuracy requires a value and source_reference")
        if self.status == "not_available" and self.value is not None:
            raise ValueError("unavailable accuracy must not carry a value")
        return self


class DurationMeasurement(_StrictFrozenModel):
    status: Literal["measured", "not_available"]
    wall_clock_seconds: float | None = Field(default=None, gt=0)
    source_reference: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> DurationMeasurement:
        if self.status == "measured" and (
            self.wall_clock_seconds is None or not self.source_reference
        ):
            raise ValueError("measured duration requires seconds and source_reference")
        if self.status == "not_available" and self.wall_clock_seconds is not None:
            raise ValueError("unavailable duration must not carry a value")
        return self


class TokenMeasurement(_StrictFrozenModel):
    status: Literal["reported", "not_available"]
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    source_reference: str | None = None
    unavailable_action_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_receipt(self) -> TokenMeasurement:
        counts = (
            self.input_tokens,
            self.output_tokens,
            self.cached_input_tokens,
            self.total_tokens,
        )
        if self.status == "not_available":
            if any(value is not None for value in counts):
                raise ValueError("unavailable token usage must not be represented as zero")
            if self.unavailable_action_count < 1:
                raise ValueError("unavailable token usage requires a missing-action count")
            return self
        if any(value is None for value in counts) or not self.source_reference:
            raise ValueError("reported token usage requires exact counts and source_reference")
        assert self.input_tokens is not None
        assert self.output_tokens is not None
        assert self.cached_input_tokens is not None
        assert self.total_tokens is not None
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        return self


class ReasoningCheckResult(_StrictFrozenModel):
    check_id: str
    passed: bool
    evidence_refs: list[str] = Field(min_length=1)


class TitanicReasoningBenchmarkRun(_StrictFrozenModel):
    """One comparable execution of the versioned Titanic reasoning challenge."""

    benchmark_id: str
    benchmark_version: str
    run_id: str
    system_revision: str
    dataset_version_id: str
    evidence_packet_hash: str
    reasoning_checks: list[ReasoningCheckResult] = Field(min_length=1)
    local_holdout_accuracy: AccuracyMeasurement
    public_accuracy: AccuracyMeasurement
    wall_clock: DurationMeasurement
    token_usage: TokenMeasurement
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_checks(self) -> TitanicReasoningBenchmarkRun:
        check_ids = [item.check_id for item in self.reasoning_checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("reasoning check IDs must be unique")
        return self

    @property
    def reasoning_accuracy(self) -> float:
        return sum(item.passed for item in self.reasoning_checks) / len(self.reasoning_checks)


class MetricComparison(_StrictFrozenModel):
    status: Literal["comparable", "not_comparable"]
    baseline: float | int | None = None
    candidate: float | int | None = None
    delta: float | int | None = None
    improved: bool | None = None
    reason: str | None = None


class TitanicReasoningComparison(_StrictFrozenModel):
    reasoning_accuracy: MetricComparison
    local_holdout_accuracy: MetricComparison
    public_accuracy: MetricComparison
    wall_clock_seconds: MetricComparison
    total_tokens: MetricComparison


def compare_titanic_reasoning_runs(
    baseline: TitanicReasoningBenchmarkRun,
    candidate: TitanicReasoningBenchmarkRun,
) -> TitanicReasoningComparison:
    """Compare like-for-like runs without inventing values for missing telemetry."""

    identity_fields = (
        "benchmark_id",
        "benchmark_version",
        "dataset_version_id",
        "evidence_packet_hash",
    )
    mismatches = [
        name for name in identity_fields if getattr(baseline, name) != getattr(candidate, name)
    ]
    baseline_checks = [item.check_id for item in baseline.reasoning_checks]
    candidate_checks = [item.check_id for item in candidate.reasoning_checks]
    if baseline_checks != candidate_checks:
        mismatches.append("reasoning_checks")
    if mismatches:
        raise ValueError("Titanic benchmark runs are not comparable: " + ", ".join(mismatches))

    return TitanicReasoningComparison(
        reasoning_accuracy=_higher_is_better(
            baseline.reasoning_accuracy, candidate.reasoning_accuracy
        ),
        local_holdout_accuracy=_optional_accuracy(
            baseline.local_holdout_accuracy, candidate.local_holdout_accuracy
        ),
        public_accuracy=_optional_accuracy(baseline.public_accuracy, candidate.public_accuracy),
        wall_clock_seconds=_optional_lower_is_better(
            baseline.wall_clock.wall_clock_seconds,
            candidate.wall_clock.wall_clock_seconds,
            "wall-clock duration was not measured for both runs",
        ),
        total_tokens=_optional_lower_is_better(
            baseline.token_usage.total_tokens,
            candidate.token_usage.total_tokens,
            "authoritative token usage was not reported for both runs",
        ),
    )


def _optional_accuracy(
    baseline: AccuracyMeasurement, candidate: AccuracyMeasurement
) -> MetricComparison:
    if baseline.value is None or candidate.value is None:
        return MetricComparison(
            status="not_comparable", reason="accuracy was not measured for both runs"
        )
    return _higher_is_better(baseline.value, candidate.value)


def _higher_is_better(baseline: float, candidate: float) -> MetricComparison:
    return MetricComparison(
        status="comparable",
        baseline=baseline,
        candidate=candidate,
        delta=candidate - baseline,
        improved=candidate > baseline,
    )


def _optional_lower_is_better(
    baseline: float | int | None,
    candidate: float | int | None,
    reason: str,
) -> MetricComparison:
    if baseline is None or candidate is None:
        return MetricComparison(status="not_comparable", reason=reason)
    return MetricComparison(
        status="comparable",
        baseline=baseline,
        candidate=candidate,
        delta=candidate - baseline,
        improved=candidate < baseline,
    )
