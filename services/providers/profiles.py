"""Provider profile loading and reference validation."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from services.contracts import ProviderProfile


def load_provider_profile(
    source: str | Path | Mapping[str, Any] | ProviderProfile,
) -> ProviderProfile:
    """Load one profile without resolving or storing credentials."""
    if isinstance(source, ProviderProfile):
        return source
    if isinstance(source, Mapping):
        return ProviderProfile.model_validate(source)
    path = Path(source)
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except OSError as exc:
        raise ValueError(f"could not read provider profile {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"provider profile {path} must contain a YAML mapping")
    return ProviderProfile.model_validate(value)


def load_provider_profiles(source: str | Path | Mapping[str, Any]) -> dict[str, ProviderProfile]:
    """Load a mapping of profile IDs to profiles from YAML or an in-memory mapping."""
    if isinstance(source, Mapping):
        raw = source
    else:
        path = Path(source)
        try:
            with path.open(encoding="utf-8") as stream:
                value = yaml.safe_load(stream)
        except OSError as exc:
            raise ValueError(f"could not read provider profiles {path}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise ValueError(f"provider profiles {path} must contain a YAML mapping")
        raw = value
    profiles = {key: load_provider_profile(value) for key, value in raw.items()}
    for key, profile in profiles.items():
        if key != profile.provider_id:
            raise ValueError(
                f"provider profile key {key!r} does not match provider_id {profile.provider_id!r}"
            )
    return profiles
