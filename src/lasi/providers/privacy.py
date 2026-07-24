"""Privacy projection for diagnostic packets before provider calls."""

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from lasi.contracts import DiagnosticPacket, ProviderProfile
from lasi.contracts.models import PrivacyMode

from .errors import ProviderPrivacyError

_MODE_RANK = {
    PrivacyMode.LOCAL_ONLY: 0,
    PrivacyMode.SUMMARY_ONLY: 1,
    PrivacyMode.PLOTS: 2,
    PrivacyMode.THUMBNAILS: 3,
    PrivacyMode.RAW_SAMPLES: 4,
    PrivacyMode.KNOWLEDGE: 5,
}

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?key|auth(?:entication|orization)?|credential|"
    r"password|passwd|private[_-]?key|secret|token|cookie|session)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:-----BEGIN [^-]+ PRIVATE KEY-----|(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+|"
    r"(?:sk|ghp|github_pat|xox[baprs])-[-A-Za-z0-9_]+|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)


def is_raw_response_reference(value: str) -> bool:
    """Identify provider response references that must not be shared as evidence."""
    return "scientist-response" in value.lower() or "raw-response" in value.lower()


def _sanitize_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {str(name): _sanitize_value(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str) and _SECRET_VALUE.search(value):
        return _SECRET_VALUE.sub(_REDACTED, value)
    return value


def sanitize_provider_payload(value: Any) -> Any:
    """Recursively remove credentials and recognizable secrets from provider payloads."""
    return _sanitize_value(value)


def filter_diagnostic_packet(
    packet: DiagnosticPacket, profile: ProviderProfile
) -> DiagnosticPacket:
    """Return a packet containing only fields permitted by the packet/profile modes."""
    if not profile.enabled:
        raise ProviderPrivacyError(f"provider profile is disabled: {profile.provider_id}")
    mode = packet.privacy_mode
    if mode == PrivacyMode.LOCAL_ONLY and profile.provider_type not in {
        "mock_provider",
        "local_model",
    }:
        raise ProviderPrivacyError("local_only privacy mode cannot call an external provider")
    capabilities = {PrivacyMode(value) for value in profile.privacy_capabilities}
    if mode != PrivacyMode.LOCAL_ONLY and mode not in capabilities:
        raise ProviderPrivacyError(f"provider does not support privacy mode {mode.value}")

    projected = sanitize_provider_payload(deepcopy(packet.model_dump(mode="python")))
    projected["artifact_refs"] = [
        ref for ref in projected.get("artifact_refs", []) if not is_raw_response_reference(ref)
    ]
    projected["knowledge_context_refs"] = [
        ref
        for ref in projected.get("knowledge_context_refs", [])
        if not is_raw_response_reference(ref)
    ]
    if _MODE_RANK[mode] < _MODE_RANK[PrivacyMode.PLOTS]:
        projected["artifact_refs"] = []
    if _MODE_RANK[mode] < _MODE_RANK[PrivacyMode.KNOWLEDGE]:
        projected["knowledge_context_refs"] = []
    return DiagnosticPacket.model_validate(projected)
