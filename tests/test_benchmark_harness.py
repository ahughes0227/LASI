from pathlib import Path

import pytest

from lasi.benchmarks.workspace import ChallengeWorkspace
from lasi.contracts import ChallengeSpec
from lasi.datasets.formats import FormatRegistry
from lasi.datasets.leakage import audit_tabular
from lasi.datasets.security import safe_extract_archive
from lasi.isolation import benchmark_default, preflight
from lasi.tabular import run_tabular_baseline
from lasi.tools import ToolContext


def _challenge() -> ChallengeSpec:
    return ChallengeSpec(
        challenge_id="local-1", project_id="p", title="Synthetic", brief="local",
        problem_type="binary_classification", modalities=["tabular"],
        train_sources=["train.csv"], test_sources=["test.csv"], target_columns=["target"],
        identifier_columns=["id"], prediction_columns=["prediction"], evaluation_metric="accuracy",
        evaluation_direction="maximize", submission_format="csv", random_seed_policy="fixed",
        external_data_policy="deny", internet_policy="deny", hidden_label_policy="evaluator_only",
    )


def test_challenge_spec_is_strict() -> None:
    with pytest.raises(ValueError):
        ChallengeSpec(**_challenge().model_dump(), unexpected=True)
    assert _challenge().challenge_id == "local-1"


def test_format_registry_and_leakage_audit(tmp_path: Path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,x,target\n1,1,yes\n2,2,no\n", encoding="utf-8")
    inspection = FormatRegistry().select(source).inspect(source)
    assert inspection.columns == ("id", "x", "target")
    audit = audit_tabular(
        [{"id": "1", "x": "1", "target": "yes"}],
        [{"id": "1", "x": "1", "target": "yes"}],
        target_columns=["target"],
    )
    assert audit.blocking


def test_archive_traversal_is_blocked(tmp_path: Path) -> None:
    import zipfile
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="traversal"):
        safe_extract_archive(archive, tmp_path / "out")


def test_workspace_input_is_hashed_and_read_only(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    workspace = ChallengeWorkspace.create(tmp_path / "workspaces")
    hashes = workspace.ingest([source])
    copied = Path(next(iter(hashes)))
    assert copied.read_bytes() == source.read_bytes()
    assert not copied.stat().st_mode & 0o222


def test_benchmark_isolation_fails_closed_defaults() -> None:
    checks = preflight(benchmark_default())
    assert all(check.passed for check in checks)
    assert benchmark_default().network == "deny_all"


def test_deterministic_tabular_baseline(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    train.write_text(
        "id,x,color,target,split\n1,0,a,no,train\n2,1,b,yes,train\n"
        "3,0,a,no,validation\n4,1,b,yes,validation\n",
        encoding="utf-8",
    )
    test.write_text("id,x,color\n5,2,a\n6,3,b\n", encoding="utf-8")
    context = ToolContext("p", "dataset-v1", "run", None, "plan", (), {
        "train_path": str(train), "test_path": str(test), "target_column": "target",
        "feature_columns": ["x", "color"], "identifier_columns": ["id"],
        "problem_type": "classification", "output_dir": str(tmp_path / "artifacts"),
    })
    result = run_tabular_baseline(context)
    assert result.metrics["accuracy"] == 1.0
    assert len(result.artifact_refs) == 3
