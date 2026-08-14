"""Load portable YAML project configuration without resolving credentials implicitly."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from services.configs.models import HostProfile, ProjectConfig, ProviderProfile

_ENV_REFERENCE = re.compile(r"^(?:env://|env:)([A-Za-z_][A-Za-z0-9_]*)$")
_ENV_TEMPLATE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _read_yaml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except OSError as exc:
        raise ValueError(f"could not read configuration {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"configuration {path} must contain a YAML mapping")
    return value


def load_project_config(
    path: str | Path,
    *,
    provider_profiles: Mapping[str, ProviderProfile | Mapping[str, Any]] | None = None,
    remote_host_profiles: Mapping[str, HostProfile | Mapping[str, Any]] | None = None,
) -> ProjectConfig:
    """Load and validate a project config, including references to external profiles."""

    config = ProjectConfig.model_validate(_read_yaml(Path(path)))
    if provider_profiles is not None:
        _validate_provider_reference(config, provider_profiles)
    if config.remote_host_profile is not None and remote_host_profiles is not None:
        _validate_host_reference(config, remote_host_profiles)
    return config


def resolve_secret_reference(
    reference: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve an explicit environment reference; never treats arbitrary text as a secret."""

    match = _ENV_REFERENCE.fullmatch(reference) or _ENV_TEMPLATE.fullmatch(reference)
    if match is None:
        raise ValueError("secret reference must use env://NAME, env:NAME, or ${NAME}")
    environment = os.environ if environ is None else environ
    name = match.group(1)
    try:
        return environment[name]
    except KeyError as exc:
        raise ValueError(f"environment secret {name!r} is not set") from exc


def _validate_provider_reference(
    config: ProjectConfig,
    profiles: Mapping[str, ProviderProfile | Mapping[str, Any]],
) -> None:
    profile = profiles.get(config.provider_profile)
    if profile is None:
        raise ValueError(f"provider profile reference not found: {config.provider_profile}")
    parsed = (
        profile if isinstance(profile, ProviderProfile) else ProviderProfile.model_validate(profile)
    )
    if parsed.provider_id != config.provider_profile:
        raise ValueError(
            f"provider profile key {config.provider_profile!r} does not match provider_id "
            f"{parsed.provider_id!r}"
        )
    if not parsed.enabled:
        raise ValueError(f"provider profile is disabled: {config.provider_profile}")


def _validate_host_reference(
    config: ProjectConfig,
    profiles: Mapping[str, HostProfile | Mapping[str, Any]],
) -> None:
    assert config.remote_host_profile is not None
    profile = profiles.get(config.remote_host_profile)
    if profile is None:
        raise ValueError(f"remote host profile reference not found: {config.remote_host_profile}")
    parsed = profile if isinstance(profile, HostProfile) else HostProfile.model_validate(profile)
    if parsed.host_profile_id != config.remote_host_profile:
        raise ValueError(
            f"remote host profile key {config.remote_host_profile!r} does not match "
            "host_profile_id "
            f"{parsed.host_profile_id!r}"
        )
    if not parsed.enabled:
        raise ValueError(f"remote host profile is disabled: {config.remote_host_profile}")
