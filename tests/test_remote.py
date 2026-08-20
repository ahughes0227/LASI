"""Focused tests for the isolated remote execution backend."""

import sys
from pathlib import Path
from typing import Any

import pytest
from services.contracts import DecisionRecord, ExperimentPlan, RemoteHostProfile, RemoteRunSpec
from services.experiments import experiment_plan_content_hash
from services.remote import (
    DEFAULT_REMOTE_TIMEOUT_SECONDS,
    InMemoryRemoteRunStore,
    LoopbackTransport,
    MockTransport,
    RemoteRunner,
)
from services.remote.models import EnvironmentCheck, TransportResult


def spec(**overrides: object) -> RemoteRunSpec:
    values: dict[str, Any] = {
        "remote_run_id": "remote-1",
        "project_id": "project-1",
        "tool_run_id": "tool-run-1",
        "host_profile_id": "host-1",
        "remote_workspace": "/runs/remote-1",
        "command": "run-tool",
        "expected_artifacts": ["metrics.json"],
    }
    values.update(overrides)
    return RemoteRunSpec(**values)


def host(**overrides: object) -> RemoteHostProfile:
    values: dict[str, Any] = {
        "host_profile_id": "host-1",
        "hostname": "worker.example",
        "username": "runner",
        "remote_workspace": "/runs",
        "trust_level": "approved_remote",
    }
    values.update(overrides)
    return RemoteHostProfile(**values)


def plan(**overrides: object) -> ExperimentPlan:
    values: dict[str, Any] = {
        "experiment_plan_id": "plan-1",
        "project_id": "project-1",
        "dataset_version": "dataset-1",
        "hypothesis": "test",
        "reason_for_experiment": "test",
        "experiment_type": "baseline",
        "execution_backend": "remote",
        "remote_host_profile": "host-1",
        "expected_signal": "test",
        "success_criteria": "test",
        "failure_criteria": "test",
        "privacy_mode": "summary_only_to_scientist",
    }
    values.update(overrides)
    return ExperimentPlan(**values)


def decision(**overrides: object) -> DecisionRecord:
    authorized_plan = plan()
    values: dict[str, Any] = {
        "decision_id": "decision-1",
        "project_id": "project-1",
        "experiment_plan_id": "plan-1",
        "experiment_plan_hash": experiment_plan_content_hash(authorized_plan),
        "risk_level": "medium",
        "decision": "allow",
        "allowed": True,
        "privacy_checks": {"privacy": True},
        "rationale": "approved for test execution",
    }
    values.update(overrides)
    return DecisionRecord(**values)


def test_mock_transport_stages_executes_retrieves_and_persists_locally(tmp_path: Path) -> None:
    def produce(_: str, workspace: Path) -> None:
        (workspace / "metrics.json").write_text("{}", encoding="utf-8")

    transport = MockTransport(tmp_path / "remote", on_execute=produce)
    store = InMemoryRemoteRunStore()
    runner = RemoteRunner(
        transport,
        store=store,
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )
    result = runner.run(
        spec(),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        tool_id="baseline",
        plan=plan(),
        decision=decision(),
    )

    assert result.status == "succeeded"
    assert result.execution_backend == "mock"
    assert Path(result.artifact_refs[0]).is_file()
    assert store.get("remote-1").markdown().startswith("# Remote Run Record")
    assert transport.commands == ["run-tool"]


def test_remote_execution_always_carries_a_bounded_timeout(tmp_path: Path) -> None:
    received: list[float] = []

    class RecordingTransport(MockTransport):
        def execute(self, command: str, workspace: str, timeout_seconds: float) -> TransportResult:
            received.append(timeout_seconds)
            return super().execute(command, workspace, timeout_seconds)

    transport = RecordingTransport(tmp_path / "remote")
    runner = RemoteRunner(
        transport,
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )

    runner.run(
        spec(),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert received == [DEFAULT_REMOTE_TIMEOUT_SECONDS]
    with pytest.raises(ValueError, match="positive wall-clock bound"):
        runner.run(
            spec(),
            host(),
            dataset_version_id="dataset-1",
            tool_version="1.0",
            plan=plan(),
            decision=decision(),
            timeout_seconds=0,
        )


def test_missing_artifact_is_explicit_partial_success(tmp_path: Path) -> None:
    runner = RemoteRunner(
        MockTransport(tmp_path / "remote"),
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )

    result = runner.run(
        spec(),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert result.status == "partial_success"
    assert result.failure_reason == "missing_expected_artifact"
    assert result.partial_success is not None


def test_environment_and_trust_failures_are_structured(tmp_path: Path) -> None:
    transport = MockTransport(
        tmp_path / "remote",
        checks=[EnvironmentCheck("python", False, "missing")],
    )
    runner = RemoteRunner(
        transport,
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )
    failed_environment = runner.run(
        spec(remote_run_id="environment"),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )
    failed_trust = runner.run(
        spec(remote_run_id="trust"),
        host(trust_level="unapproved_remote"),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert failed_environment.failure_reason == "environment_validation_failed"
    assert failed_trust.failure_reason == "permission_denied"


def test_loopback_executes_only_on_localhost_and_timeout_is_recorded(tmp_path: Path) -> None:
    transport = LoopbackTransport(tmp_path / "remote", result=TransportResult(0))
    runner = RemoteRunner(
        transport,
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )
    command = f'"{sys.executable}" -c "print(\'ok\')"'
    result = runner.run(
        spec(remote_run_id="loopback", command=command),
        host(hostname="localhost", trust_level="local_machine"),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert result.status == "partial_success"
    assert result.errors == []


def test_loopback_rejects_shell_metacharacters_without_running_them(tmp_path: Path) -> None:
    marker = tmp_path / "created-by-shell"
    transport = LoopbackTransport(tmp_path / "remote")
    runner = RemoteRunner(
        transport, bundle_root=tmp_path / "bundles", artifact_root=tmp_path / "artifacts"
    )

    result = runner.run(
        spec(remote_run_id="unsafe", command=f'echo safe; echo hacked > "{marker}"'),
        host(hostname="localhost", trust_level="local_machine"),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert result.status == "failed"
    assert not marker.exists()
    assert "shell syntax" in result.errors[0]


def test_remote_runner_requires_plan_and_decision_authorization(tmp_path: Path) -> None:
    runner = RemoteRunner(
        MockTransport(tmp_path / "remote"),
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )

    result = runner.run(
        spec(remote_run_id="unauthorized"),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
    )

    assert result.failure_reason == "permission_denied"
    assert "authorization" in result.errors[0]


def test_input_transfer_requires_policy_and_privacy_approval(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("sensitive", encoding="utf-8")
    runner = RemoteRunner(
        MockTransport(tmp_path / "remote"),
        bundle_root=tmp_path / "bundles",
        artifact_root=tmp_path / "artifacts",
    )

    result = runner.run(
        spec(remote_run_id="blocked-transfer"),
        host(data_transfer_policy="local_only"),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        input_paths=[source],
        plan=plan(),
        decision=decision(),
    )

    assert result.failure_reason == "permission_denied"
    assert "transfer" in result.errors[0]
    assert not (tmp_path / "remote" / "runs" / "remote-1" / "input.txt").exists()


def test_secrets_are_redacted_from_persisted_logs(tmp_path: Path) -> None:
    transport = MockTransport(
        tmp_path / "remote",
        result=TransportResult(1, "token=top-secret", "Authorization: Bearer abc123"),
    )
    runner = RemoteRunner(
        transport, bundle_root=tmp_path / "bundles", artifact_root=tmp_path / "artifacts"
    )

    result = runner.run(
        spec(remote_run_id="redacted"),
        host(),
        dataset_version_id="dataset-1",
        tool_version="1.0",
        plan=plan(),
        decision=decision(),
    )

    assert result.status == "failed"
    log = (tmp_path / "bundles" / "redacted" / "stdout.log").read_text(encoding="utf-8")
    error_log = (tmp_path / "bundles" / "redacted" / "stderr.log").read_text(encoding="utf-8")
    assert "top-secret" not in log
    assert "abc123" not in error_log
    assert "[REDACTED]" in log
    assert "[REDACTED]" in error_log
