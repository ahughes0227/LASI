"""Artifact capture boundary used by scientist providers."""

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Protocol

from .privacy import sanitize_provider_payload


class ArtifactSink(Protocol):
    """Storage abstraction; implementations may delegate to MLflow or a file store."""

    def capture_raw_response(
        self, response: object, *, provider_id: str, metadata: Mapping[str, str]
    ) -> str: ...


class MemoryArtifactSink:
    """Deterministic in-memory sink for tests and local provider use."""

    def __init__(self) -> None:
        self.responses: dict[str, object] = {}

    def capture_raw_response(
        self, response: object, *, provider_id: str, metadata: Mapping[str, str]
    ) -> str:
        safe_response = sanitize_provider_payload(response)
        payload = json.dumps(safe_response, sort_keys=True, default=str, separators=(",", ":"))
        digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
        artifact_id = f"artifact://scientist-response/{provider_id}/{digest}"
        self.responses[artifact_id] = {
            "response": safe_response,
            "metadata": dict(sanitize_provider_payload(dict(metadata))),
        }
        return artifact_id


class NullArtifactSink:
    """Explicit no-op sink for callers that do not retain artifacts."""

    def capture_raw_response(
        self, response: object, *, provider_id: str, metadata: Mapping[str, str]
    ) -> str:
        del response, provider_id, metadata
        return "artifact://unrecorded/scientist-response"
