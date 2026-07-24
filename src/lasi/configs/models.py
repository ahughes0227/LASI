"""Typed models for configuration-owned settings and profile references."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderType = Literal[
    "mock_provider",
    "local_model",
    "vertex",
    "openai",
    "anthropic",
    "internal_api",
    "future_provider",
]
TrustLevel = Literal[
    "local_machine",
    "trusted_internal",
    "approved_remote",
    "unapproved_remote",
    "external_cloud",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_StrictModel):
    """Portable project settings; credentials and profile details do not belong here."""

    config_version: str = "1"
    project_id: str = Field(min_length=1)
    provider_profile: str = Field(min_length=1)
    remote_host_profile: str | None = None
    privacy_mode: str = "local_only"
    evaluation_policy: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("remote_host_profile")
    @classmethod
    def reject_empty_host_reference(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("remote_host_profile must be a non-empty profile ID")
        return value


class ProviderProfile(_StrictModel):
    """A provider profile stored outside portable project configuration."""

    provider_id: str = Field(min_length=1)
    provider_type: ProviderType
    model_name: str | None = None
    endpoint: str | None = None
    authentication_reference: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    determinism_settings: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=60, gt=0)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    token_budget: int | None = Field(default=None, ge=0)
    privacy_capabilities: list[str] = Field(default_factory=list)
    allowed_input_types: list[str] = Field(default_factory=list)
    response_format: str | None = None
    enabled: bool = True


class HostProfile(_StrictModel):
    """A remote host profile stored outside portable project configuration."""

    host_profile_id: str = Field(min_length=1)
    hostname: str = Field(min_length=1)
    username: str = Field(min_length=1)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    authentication_reference: str | None = None
    remote_workspace: str = Field(min_length=1)
    environment_setup_command: str | None = None
    python_command: str = "python"
    hardware_summary: dict[str, Any] = Field(default_factory=dict)
    data_transfer_policy: str = "not_transferred_due_to_policy"
    trust_level: TrustLevel
    enabled: bool = True
