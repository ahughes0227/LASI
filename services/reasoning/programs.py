"""Reasoning programs and the provider that runs them.

A program produces a provider-shaped response; everything downstream — normalisation,
privacy filtering, artifact capture — is the existing provider path, unchanged.  That is
what keeps an LM-backed reviewer interchangeable with the mock one.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from services.contracts import DiagnosticPacket, ProviderProfile
from services.providers.artifacts import ArtifactSink, MemoryArtifactSink
from services.providers.normalization import normalize_review
from services.providers.privacy import filter_diagnostic_packet


@runtime_checkable
class ReasoningProgram(Protocol):
    """Produces a raw provider response for a diagnostic packet.

    Deliberately returns the raw shape rather than a `ScientistReview`: normalisation is
    where provider output is validated and made trustworthy, and a program that could
    return a finished contract would bypass it.
    """

    program_id: str
    program_version: str

    def respond(self, packet: DiagnosticPacket, *, experiment_ids: list[str]) -> dict[str, Any]: ...


class ReasoningScientistProvider:
    """Runs a `ReasoningProgram` behind the ordinary `ScientistProvider` interface.

    Recommendation-only, like every provider: no tool, decision, or persistence access.
    """

    def __init__(
        self,
        profile: ProviderProfile,
        program: ReasoningProgram,
        *,
        artifact_sink: ArtifactSink | None = None,
    ) -> None:
        self.profile = profile
        self.program = program
        self.artifact_sink = artifact_sink or MemoryArtifactSink()

    def review(
        self,
        packet: DiagnosticPacket,
        *,
        experiment_ids: list[str] | None = None,
        prompt_template_version: str = "1.0",
    ) -> Any:
        # Filter before the program sees it: an LM program must not receive fields the
        # provider profile forbids, and doing this after the call would be too late.
        filtered = filter_diagnostic_packet(packet, self.profile)
        raw = self.program.respond(filtered, experiment_ids=experiment_ids or [])
        artifact = self.artifact_sink.capture_raw_response(
            raw,
            provider_id=self.profile.provider_id,
            metadata={
                "diagnostic_packet_id": packet.diagnostic_packet_id,
                "prompt_template_version": prompt_template_version,
                "program_id": self.program.program_id,
                "program_version": self.program.program_version,
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
