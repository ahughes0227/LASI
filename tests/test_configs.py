"""Focused tests for portable project configuration."""

from pathlib import Path

import pytest
from services.configs import (
    HostProfile,
    ProviderProfile,
    load_project_config,
    resolve_secret_reference,
)


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "project.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def provider() -> ProviderProfile:
    return ProviderProfile(provider_id="mock", provider_type="mock_provider")


def host() -> HostProfile:
    return HostProfile(
        host_profile_id="gpu-1",
        hostname="gpu.example",
        username="runner",
        remote_workspace="/runs",
        trust_level="approved_remote",
    )


def test_loads_config_and_validates_external_profile_references(tmp_path: Path) -> None:
    config = load_project_config(
        write_config(
            tmp_path,
            "project_id: demo\nprovider_profile: mock\nremote_host_profile: gpu-1\n",
        ),
        provider_profiles={"mock": provider()},
        remote_host_profiles={"gpu-1": host()},
    )
    assert config.project_id == "demo"
    assert config.provider_profile == "mock"


def test_rejects_unknown_profile_reference(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provider profile reference not found"):
        load_project_config(
            write_config(tmp_path, "project_id: demo\nprovider_profile: missing\n"),
            provider_profiles={"mock": provider()},
        )


def test_rejects_unknown_remote_host_reference(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="remote host profile reference not found"):
        load_project_config(
            write_config(
                tmp_path,
                "project_id: demo\nprovider_profile: mock\nremote_host_profile: missing\n",
            ),
            provider_profiles={"mock": provider()},
            remote_host_profiles={},
        )


def test_secret_reference_requires_explicit_environment_syntax() -> None:
    assert resolve_secret_reference("env://TOKEN", environ={"TOKEN": "secret"}) == "secret"
    assert resolve_secret_reference("${TOKEN}", environ={"TOKEN": "secret"}) == "secret"
    with pytest.raises(ValueError, match="must use"):
        resolve_secret_reference("plain-secret", environ={"TOKEN": "secret"})


def test_config_forbids_credentials(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="extra_forbidden"):
        load_project_config(
            write_config(
                tmp_path,
                "project_id: demo\nprovider_profile: mock\napi_key: accidentally-portable\n",
            ),
            provider_profiles={"mock": provider()},
        )
