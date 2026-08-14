"""Adapters that expose structured memory as references for context assembly."""

from __future__ import annotations

from typing import Protocol

from services.memory import (
    Artifact,
    Decision,
    ExperimentPlan,
    OperationalMemory,
    Report,
    ScientistReview,
    ToolRun,
)

from .models import ContextRequest


class StructuredMemoryRetriever(Protocol):
    """Returns bounded machine-native references; it never serializes raw state into ICM."""

    def retrieve_refs(self, request: ContextRequest) -> list[str]: ...


class OperationalMemoryRetriever:
    """Selects project-scoped SQL records as opaque references for an action."""

    def __init__(self, memory: OperationalMemory, *, limit: int = 12) -> None:
        self.memory = memory
        self.limit = limit

    def retrieve_refs(self, request: ContextRequest) -> list[str]:
        records: list[tuple[str, str]] = []
        for record_type, field in (
            (ExperimentPlan, "experiment_plan_id"),
            (ToolRun, "tool_run_id"),
            (ScientistReview, "review_id"),
            (Decision, "decision_id"),
            (Artifact, "artifact_id"),
            (Report, "report_id"),
        ):
            for record in self.memory.list_for_project(record_type, request.project_id):
                records.append((record_type.__tablename__, str(getattr(record, field))))
        refs = [f"sql://{table}/{record_id}" for table, record_id in sorted(records)]
        return refs[: self.limit]
