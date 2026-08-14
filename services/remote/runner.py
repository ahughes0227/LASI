"""Auditable remote execution service behind the canonical tool result."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from services.contracts import (
    DecisionRecord,
    ExperimentPlan,
    RemoteHostProfile,
    RemoteRunSpec,
    ToolRunResult,
)

from .models import CleanupResult, RemoteRunRecord, RemoteRunState, TransportResult
from .persistence import InMemoryRemoteRunStore, RemoteRunStore
from .transports import LoopbackTransport, MockTransport, RemoteTransport


class RemoteRunner:
    """Execute an explicit run spec while keeping all authoritative state local."""

    def __init__(
        self,
        transport: RemoteTransport,
        *,
        store: RemoteRunStore | None = None,
        bundle_root: Path | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        if not isinstance(transport, (MockTransport, LoopbackTransport)):
            raise ValueError("only MockTransport and LoopbackTransport are permitted")
        self.transport = transport
        self.store = store or InMemoryRemoteRunStore()
        self.bundle_root = bundle_root or Path.cwd() / ".lasi-remote-bundles"
        self.artifact_root = artifact_root or Path.cwd() / ".lasi-remote-artifacts"

    def run(
        self,
        spec: RemoteRunSpec,
        host: RemoteHostProfile,
        *,
        dataset_version_id: str,
        tool_version: str,
        tool_id: str = "remote_tool",
        input_paths: list[Path] | None = None,
        timeout_seconds: float | None = None,
        plan: ExperimentPlan | None = None,
        decision: DecisionRecord | None = None,
    ) -> ToolRunResult:
        started_at = datetime.now(UTC)
        started = monotonic()
        bundle = (self.bundle_root / spec.remote_run_id).resolve()
        bundle.mkdir(parents=True, exist_ok=True)
        record = RemoteRunRecord(
            remote_run_id=spec.remote_run_id,
            project_id=spec.project_id,
            experiment_id=spec.experiment_id,
            tool_run_id=spec.tool_run_id,
            host_profile_id=host.host_profile_id,
            hostname=host.hostname,
            remote_workspace=spec.remote_workspace,
            command=spec.command,
            environment_setup=spec.environment_setup,
            cleanup_policy=spec.cleanup_policy,
            provenance={
                "transport": type(self.transport).__name__,
                "tool_version": tool_version,
                "tool_id": tool_id,
                "backend": self._backend_name(),
            },
            bundle_path=bundle,
            start_time=started_at,
        )
        self.store.save(record)
        try:
            self._authorize(spec, host, plan, decision)
            self._validate_host(host)
            self._validate_workspace(spec, host)
            record.state = RemoteRunState.STAGING
            self.store.save(record)
            self.transport.prepare_workspace(spec.remote_workspace)
            staged = input_paths or []
            self._authorize_transfer(spec, host, decision, staged, plan)
            for source in staged:
                if not source.is_file():
                    return self._finish_failure(
                        record,
                        dataset_version_id,
                        tool_version,
                        started,
                        "staging_failed",
                        f"input does not exist: {source}",
                    )
                relative = source.name
                self.transport.stage(source, spec.remote_workspace, relative)
                record.staged_inputs.append(relative)
            self._write_bundle_manifest(bundle, spec, host, record.staged_inputs)
            record.state = RemoteRunState.STAGED
            self.store.save(record)

            record.state = RemoteRunState.ENVIRONMENT_CHECKING
            record.environment_checks = self.transport.check_environment(
                spec.remote_workspace,
                host.python_command,
                spec.environment_setup,
            )
            self.store.save(record)
            failed_checks = [check for check in record.environment_checks if not check.passed]
            if failed_checks:
                return self._finish_failure(
                    record,
                    dataset_version_id,
                    tool_version,
                    started,
                    "environment_validation_failed",
                    "; ".join(f"{check.name}: {check.detail}" for check in failed_checks),
                )

            record.state = RemoteRunState.RUNNING
            self.store.save(record)
            command = self._command(spec)
            result = self.transport.execute(command, spec.remote_workspace, timeout_seconds)
            record.exit_code = result.exit_code
            self._capture_logs(record, result)
            if result.timed_out:
                return self._finish_failure(
                    record,
                    dataset_version_id,
                    tool_version,
                    started,
                    "timeout",
                    "remote command timed out",
                    status="timed_out",
                )
            if result.exit_code != 0:
                return self._finish_failure(
                    record,
                    dataset_version_id,
                    tool_version,
                    started,
                    "command_failed",
                    self._redact(result.stderr or "remote command failed"),
                )

            record.state = RemoteRunState.RETRIEVING_ARTIFACTS
            self.store.save(record)
            missing = self._retrieve_artifacts(record, spec)
            record.missing_artifacts = missing
            status = "partial_success" if missing else "succeeded"
            record.state = RemoteRunState.PARTIAL_SUCCESS if missing else RemoteRunState.SUCCEEDED
            if missing:
                record.failure_reason = "missing_expected_artifact"
                record.retry_suggested = False
            return self._finish(record, dataset_version_id, tool_version, started, status)
        except PermissionError as exc:
            return self._finish_failure(
                record, dataset_version_id, tool_version, started, "permission_denied", str(exc)
            )
        except FileNotFoundError as exc:
            return self._finish_failure(
                record,
                dataset_version_id,
                tool_version,
                started,
                "artifact_retrieval_failed",
                str(exc),
            )
        except RuntimeError as exc:
            message = str(exc)
            reason, _, detail = message.partition(": ")
            if reason not in {
                "host_profile_disabled",
                "permission_denied",
                "ssh_connection_failed",
                "workspace_creation_failed",
            }:
                reason, detail = "unknown_remote_error", message
            return self._finish_failure(
                record, dataset_version_id, tool_version, started, reason, detail or message
            )
        except Exception as exc:  # noqa: BLE001 - execution failures are evidence.
            return self._finish_failure(
                record, dataset_version_id, tool_version, started, "unknown_remote_error", str(exc)
            )

    def _validate_host(self, host: RemoteHostProfile) -> None:
        if not host.enabled:
            raise RuntimeError("host_profile_disabled: host profile is disabled")
        if host.trust_level not in {"local_machine", "trusted_internal", "approved_remote"}:
            raise RuntimeError("permission_denied: host trust level is not approved")
        if isinstance(self.transport, LoopbackTransport) and host.hostname not in {
            "localhost",
            "127.0.0.1",
        }:
            raise RuntimeError(
                "ssh_connection_failed: loopback transport requires a loopback hostname",
            )

    @staticmethod
    def _authorize(
        spec: RemoteRunSpec,
        host: RemoteHostProfile,
        plan: ExperimentPlan | None,
        decision: DecisionRecord | None,
    ) -> None:
        if plan is None or decision is None:
            raise PermissionError("plan and decision authorization are required")
        if plan.project_id != spec.project_id or decision.project_id != spec.project_id:
            raise PermissionError("authorization project does not match remote run")
        if decision.experiment_plan_id != plan.experiment_plan_id:
            raise PermissionError("decision does not authorize the experiment plan")
        if plan.remote_host_profile and plan.remote_host_profile != host.host_profile_id:
            raise PermissionError("experiment plan does not authorize this host")
        if plan.execution_backend != "remote":
            raise PermissionError("experiment plan does not authorize remote execution")
        if not decision.allowed or decision.decision not in {"allow", "allow_with_warning"}:
            raise PermissionError("remote execution is not allowed by the decision record")
        if (plan.approval_required or decision.approval_required) and not decision.approved_by:
            raise PermissionError("required approval is missing")

    @staticmethod
    def _authorize_transfer(
        spec: RemoteRunSpec,
        host: RemoteHostProfile,
        decision: DecisionRecord | None,
        staged: list[Path],
        plan: ExperimentPlan | None,
    ) -> None:
        if not staged:
            return
        if decision is None or plan is None:
            raise PermissionError("input transfer requires an approved decision")
        policy = (host.data_transfer_policy or "").strip().lower()
        allowed_policies = {
            "allowed",
            "approved",
            "copy",
            "raw_data_allowed",
            "copied_with_run_bundle",
            "referenced_from_remote_cache",
            "referenced_from_shared_storage",
        }
        if policy not in allowed_policies:
            raise PermissionError("input transfer is blocked by host data-transfer policy")
        if not bool(decision.privacy_checks.get("privacy", False)):
            raise PermissionError("input transfer is blocked by privacy checks")
        if spec.dataset_transfer_mode and spec.dataset_transfer_mode not in {
            "copied_with_run_bundle",
            "referenced_from_remote_cache",
            "referenced_from_shared_storage",
        }:
            raise PermissionError("unsupported dataset transfer mode")
        if plan.privacy_mode.value == "local_only":
            raise PermissionError("local-only privacy mode forbids input transfer")

    def _backend_name(self) -> str:
        if isinstance(self.transport, LoopbackTransport):
            return "loopback"
        return "mock"

    @staticmethod
    def _validate_workspace(spec: RemoteRunSpec, host: RemoteHostProfile) -> None:
        base = host.remote_workspace.rstrip("/") or "/"
        workspace = spec.remote_workspace.rstrip("/") or "/"
        if workspace != base and not workspace.startswith(base + "/"):
            raise RuntimeError("workspace_creation_failed: run workspace is outside host workspace")

    @staticmethod
    def _command(spec: RemoteRunSpec) -> str:
        parts = [spec.environment_setup, spec.command]
        return " && ".join(part for part in parts if part)

    @staticmethod
    def _write_bundle_manifest(
        bundle: Path, spec: RemoteRunSpec, host: RemoteHostProfile, staged: list[str]
    ) -> None:
        (bundle / "run_spec.json").write_text(
            json.dumps(
                {
                    "run_spec": spec.model_dump(mode="json"),
                    "host_profile_id": host.host_profile_id,
                    "staged_inputs": staged,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _capture_logs(self, record: RemoteRunRecord, result: TransportResult) -> None:
        assert record.bundle_path is not None
        stdout = record.bundle_path / "stdout.log"
        stderr = record.bundle_path / "stderr.log"
        run_log = record.bundle_path / "run_log.txt"
        stdout.write_text(self._redact(result.stdout), encoding="utf-8")
        stderr.write_text(self._redact(result.stderr), encoding="utf-8")
        run_log.write_text(self._redact(result.stdout + result.stderr), encoding="utf-8")
        record.logs_uri = [str(stdout), str(stderr), str(run_log)]

    def _retrieve_artifacts(self, record: RemoteRunRecord, spec: RemoteRunSpec) -> list[str]:
        assert record.bundle_path is not None
        destination_root = self.artifact_root / record.remote_run_id
        missing: list[str] = []
        for artifact in spec.expected_artifacts:
            destination = destination_root / artifact
            resolved = destination.resolve()
            root = destination_root.resolve()
            if resolved != root and root not in resolved.parents:
                missing.append(artifact)
                continue
            try:
                self.transport.retrieve(spec.remote_workspace, artifact, destination)
            except FileNotFoundError:
                missing.append(artifact)
            else:
                record.retrieved_artifacts.append(str(destination))
        return missing

    def _finish_failure(
        self,
        record: RemoteRunRecord,
        dataset_version_id: str,
        tool_version: str,
        started: float,
        reason: str,
        detail: str,
        *,
        status: str = "failed",
    ) -> ToolRunResult:
        record.failure_reason = reason
        record.provenance["failure_detail"] = self._redact(detail)
        record.state = RemoteRunState(status)
        return self._finish(record, dataset_version_id, tool_version, started, status)

    def _finish(
        self,
        record: RemoteRunRecord,
        dataset_version_id: str,
        tool_version: str,
        started: float,
        status: str,
    ) -> ToolRunResult:
        end = datetime.now(UTC)
        cleanup = self._cleanup(record, status)
        record.cleanup = cleanup
        record.end_time = end
        if record.bundle_path is not None:
            (record.bundle_path / "remote_run_record.md").write_text(
                record.markdown(),
                encoding="utf-8",
            )
        self.store.save(record)
        partial = None
        if status == "partial_success":
            partial = {
                "what_succeeded": record.retrieved_artifacts,
                "what_failed": record.missing_artifacts,
                "missing_artifacts": record.missing_artifacts,
                "can_continue": False,
            }
        return ToolRunResult(
            tool_run_id=record.tool_run_id,
            project_id=record.project_id,
            experiment_id=record.experiment_id,
            dataset_version_id=dataset_version_id,
            tool_id=record.provenance.get("tool_id", "remote_tool"),
            tool_version=tool_version,
            input_refs=record.staged_inputs,
            output_refs=record.retrieved_artifacts,
            parameters={
                "remote_run_id": record.remote_run_id,
                "host_profile_id": record.host_profile_id,
            },
            execution_backend=self._backend_name(),
            status=status,
            start_time=record.start_time,
            end_time=end,
            runtime_seconds=monotonic() - started,
            warnings=[],
            errors=[record.provenance["failure_detail"]]
            if "failure_detail" in record.provenance
            else [],
            artifact_refs=record.retrieved_artifacts + record.logs_uri,
            failure_reason=record.failure_reason,
            partial_success=partial,
        )

    @staticmethod
    def _redact(value: str) -> str:
        patterns = (
            r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[=:]\s*)[^\s,;]+",
            r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+",
        )
        for pattern in patterns:
            value = re.sub(pattern, r"\1[REDACTED]", value)
        return value

    def _cleanup(self, record: RemoteRunRecord, status: str) -> CleanupResult:
        # The transport is never allowed to mutate local persistence; cleanup
        # status is recorded here afterward.
        if record.cleanup_policy == "keep_all":
            return CleanupResult(attempted=False, succeeded=True, detail="keep_all")
        if record.cleanup_policy == "delete_after_success" and status != "succeeded":
            return CleanupResult(attempted=False, succeeded=True, detail="success_not_reached")
        if record.cleanup_policy not in {"delete_after_success", "delete_after_retrieval"}:
            return CleanupResult(attempted=False, succeeded=True, detail=record.cleanup_policy)
        try:
            self.transport.cleanup(record.remote_workspace)
        except Exception as exc:  # noqa: BLE001 - cleanup is separately recorded.
            record.failure_reason = record.failure_reason or "cleanup_failed"
            return CleanupResult(attempted=True, succeeded=False, detail=str(exc))
        return CleanupResult(attempted=True, succeeded=True, detail=record.cleanup_policy)
