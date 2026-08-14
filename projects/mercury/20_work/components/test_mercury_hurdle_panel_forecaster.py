"""Synthetic acceptance tests for the project-local Mercury hurdle component."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from services.components.execution import ComponentExecutionContext


SOURCE = Path(__file__).with_name("mercury_hurdle_panel_forecaster.py")
SPEC = importlib.util.spec_from_file_location("mercury_hurdle_component", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _panel(path: Path) -> None:
    rows = []
    for store in (1, 2):
        for family in ("A", "B"):
            for day in pd.date_range("2017-01-01", "2017-02-14"):
                offset = (day - pd.Timestamp("2017-01-01")).days
                sales = 0.0 if (offset + store) % 5 == 0 else float(2 + store + (offset % 4))
                rows.append({"date": day, "store_nbr": store, "family": family, "sales": sales})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_hurdle_component_is_past_only_nonnegative_and_deterministic(tmp_path: Path) -> None:
    train = tmp_path / "synthetic-panel.csv"
    _panel(train)
    config = MODULE.MercuryHurdlePanelConfig(train_end_date="2017-01-30", validation_start_date="2017-01-31", validation_end_date="2017-02-14", horizon_days=15, training_window_days=30, max_rows_per_horizon=500, max_iter=10)
    def run(name: str):
        root = tmp_path / name
        root.mkdir()
        return MODULE.run_mercury_hurdle_panel_forecaster(ComponentExecutionContext(project_id="mercury", dataset_version_id="synthetic", experiment_spec_id="synthetic-hurdle", node_id="hurdle", workdir=root, inputs={"train_panel_csv": train}, config=config, random_seed=7))
    first, second = run("first"), run("second")
    a = pd.read_csv(first.outputs["validation_predictions"])
    b = pd.read_csv(second.outputs["validation_predictions"])
    assert np.array_equal(a["prediction"].to_numpy(), b["prediction"].to_numpy())
    assert (a["prediction"] >= 0).all()
    lineage = json.loads(first.outputs["feature_lineage"].read_text())
    assert all(item["past_only"] for item in lineage["horizons"])
    assert all(item["feature_max_source_date"] < item["target_date"] for item in lineage["horizons"])
    evaluation = json.loads(first.outputs["evaluation"].read_text())
    assert evaluation["zero_target_rows"] > 0 and evaluation["positive_target_rows"] > 0


def test_hurdle_component_rejects_missing_declared_panel_input(tmp_path: Path) -> None:
    config = MODULE.MercuryHurdlePanelConfig(
        train_end_date="2017-01-30",
        validation_start_date="2017-01-31",
        validation_end_date="2017-02-14",
        horizon_days=15,
        training_window_days=30,
        max_rows_per_horizon=500,
        max_iter=10,
    )
    with __import__("pytest").raises(ValueError, match="train_panel_csv"):
        MODULE.run_mercury_hurdle_panel_forecaster(
            ComponentExecutionContext(
                project_id="mercury", dataset_version_id="synthetic", experiment_spec_id="synthetic-hurdle",
                node_id="hurdle", workdir=tmp_path, inputs={}, config=config, random_seed=7,
            )
        )
