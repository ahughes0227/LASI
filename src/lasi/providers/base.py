"""Stable interface shared by all scientist providers."""

from typing import Protocol

from lasi.contracts import DiagnosticPacket, ScientistReview


class ScientistProvider(Protocol):
    def review(
        self,
        packet: DiagnosticPacket,
        *,
        experiment_ids: list[str] | None = None,
        prompt_template_version: str = "1.0",
    ) -> ScientistReview: ...
