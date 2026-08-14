"""Operational records for remote execution."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class RemoteRunState(StrEnum):
    PLANNED = "planned"
    STAGING = "staging"
    STAGED = "staged"
    ENVIRONMENT_CHECKING = "environment_checking"
    RUNNING = "running"
    RETRIEVING_ARTIFACTS = "retrieving_artifacts"
    SUCCEEDED = "succeeded"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CLEANUP_PENDING = "cleanup_pending"


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class TransportResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class CleanupResult:
    attempted: bool
    succeeded: bool
    detail: str = ""


@dataclass
class RemoteRunRecord:
    remote_run_id: str
    project_id: str
    experiment_id: str | None
    tool_run_id: str
    host_profile_id: str
    hostname: str
    remote_workspace: str
    command: str
    environment_setup: str | None
    state: RemoteRunState = RemoteRunState.PLANNED
    start_time: datetime | None = None
    end_time: datetime | None = None
    exit_code: int | None = None
    logs_uri: list[str] = field(default_factory=list)
    staged_inputs: list[str] = field(default_factory=list)
    retrieved_artifacts: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    retry_suggested: bool = False
    cleanup_policy: str = "keep_all"
    cleanup: CleanupResult = field(default_factory=lambda: CleanupResult(False, True))
    environment_checks: list[EnvironmentCheck] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    bundle_path: Path | None = None

    def markdown(self) -> str:
        """Render the stable skill output without inventing unrecorded facts."""
        artifacts = "\n".join(f"- {item}" for item in self.retrieved_artifacts) or "- none"
        logs = "\n".join(f"- {item}" for item in self.logs_uri) or "- none"
        failure = self.failure_reason or "none"
        provenance = ", ".join(f"{key}={value}" for key, value in self.provenance.items()) or "none"
        return (
            "# Remote Run Record\n\n"
            f"- project_id: {self.project_id}\n"
            f"- experiment_id: {self.experiment_id or 'none'}\n"
            f"- host_profile: {self.host_profile_id}\n"
            f"- command: {self.command}\n"
            f"- start_time: {self.start_time or 'none'}\n"
            f"- end_time: {self.end_time or 'none'}\n"
            f"- exit_code: {self.exit_code if self.exit_code is not None else 'none'}\n"
            f"- state: {self.state.value}\n"
            f"- failure_reason: {failure}\n"
            f"- retry_suggested: {self.retry_suggested}\n"
            f"- logs_uri:\n{logs}\n"
            f"- artifacts:\n{artifacts}\n"
            f"- provenance: {provenance}\n"
        )
