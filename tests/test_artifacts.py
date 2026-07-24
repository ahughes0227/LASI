"""Tests for the local MLflow artifact adapter."""

from pathlib import Path

import pytest

from lasi.core.artifacts import ArtifactPolicyError, MlflowArtifactStore


def test_local_mlflow_artifact_round_trip_preserves_provenance(tmp_path: Path) -> None:
    store = MlflowArtifactStore(tmp_path / "mlruns", experiment_name="artifact-tests")
    source = tmp_path / "report.html"
    source.write_text("<h1>evidence</h1>", encoding="utf-8")

    with store.start_run("report", {"project_id": "project-1"}) as run:
        record = store.log_file(
            run,
            source,
            artifact_type="report",
            artifact_path="reports/report.html",
            project_id="project-1",
            dataset_version_id="dataset:v1",
            experiment_id="experiment-1",
            tool_run_id="tool-run-1",
            report_id="report-1",
        )

    assert record.artifact_uri == f"runs:/{run.run_id}/reports/report.html"
    assert record.project_id == "project-1"
    assert record.dataset_version_id == "dataset:v1"
    assert record.experiment_id == "experiment-1"
    assert record.tool_run_id == "tool-run-1"
    assert record.report_id == "report-1"
    assert store.download(record).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_log_json_creates_immutable_contract_record(tmp_path: Path) -> None:
    store = MlflowArtifactStore(tmp_path / "mlruns")
    with store.start_run("json") as run:
        record = store.log_json(
            run, {"metric": 0.9}, filename="metrics.json", artifact_type="metrics"
        )

    assert record.immutable is True
    assert record.artifact_type == "metrics"
    assert record.checksum is not None
    assert store.download(record).name == "metrics.json"


@pytest.mark.parametrize(
    "artifact_path", ["../secret.txt", "/absolute.txt", "nested\\escape.txt", "C:/escape.txt"]
)
def test_artifact_paths_must_be_safe_relative_paths(tmp_path: Path, artifact_path: str) -> None:
    store = MlflowArtifactStore(tmp_path / "mlruns")
    source = tmp_path / "evidence.txt"
    source.write_text("safe", encoding="utf-8")
    with store.start_run("unsafe-path") as run:
        with pytest.raises(ArtifactPolicyError):
            store.log_file(run, source, artifact_type="evidence", artifact_path=artifact_path)


@pytest.mark.parametrize("filename", [".env", "credentials.json", "config.yaml", "private.pem"])
def test_sensitive_artifact_filenames_are_rejected(tmp_path: Path, filename: str) -> None:
    store = MlflowArtifactStore(tmp_path / "mlruns")
    with store.start_run("unsafe-file") as run:
        with pytest.raises(ArtifactPolicyError):
            store.log_bytes(run, b"safe", filename=filename, artifact_type="evidence")


def test_secret_like_artifact_content_is_rejected(tmp_path: Path) -> None:
    store = MlflowArtifactStore(tmp_path / "mlruns")
    with store.start_run("secret-content") as run:
        with pytest.raises(ArtifactPolicyError):
            store.log_bytes(
                run, b"api_key = 'super-secret-value'", filename="notes.txt", artifact_type="text"
            )
