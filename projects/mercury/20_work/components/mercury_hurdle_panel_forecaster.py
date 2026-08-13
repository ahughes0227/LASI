"""Project-local, past-only hurdle forecaster for Mercury research only.

This module is deliberately not part of the shared LASI toolbox.  Its sole
public handler is ``run_mercury_hurdle_panel_forecaster``; it performs no I/O
outside the component execution workdir apart from the declared immutable
training-panel input.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_log_error

from services.components.execution import ComponentExecutionContext, ComponentRunOutput


class MercuryHurdlePanelConfig(BaseModel):
    """Fixed direct-horizon, local-only configuration for the Mercury panel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train_end_date: str
    validation_start_date: str
    validation_end_date: str
    horizon_days: int = Field(default=16, ge=1, le=31)
    training_window_days: int = Field(default=730, ge=30, le=1095)
    max_rows_per_horizon: int = Field(default=30_000, ge=100, le=100_000)
    max_iter: int = Field(default=120, ge=10, le=500)
    learning_rate: float = Field(default=0.08, gt=0, le=1)
    max_leaf_nodes: int = Field(default=31, ge=2, le=255)
    l2_regularization: float = Field(default=1.0, ge=0)


def run_mercury_hurdle_panel_forecaster(context: ComponentExecutionContext) -> ComponentRunOutput:
    """Fit direct horizon occurrence/magnitude models from strictly prior sales."""

    config: MercuryHurdlePanelConfig = context.config
    panel_path = context.inputs.get("train_panel_csv")
    if panel_path is None:
        raise ValueError("declared train_panel_csv input is required")
    panel_path = Path(panel_path).resolve()
    if not panel_path.is_file():
        raise FileNotFoundError("declared training panel is unavailable")
    frame = pd.read_csv(panel_path, parse_dates=["date"])
    required = {"date", "store_nbr", "family", "sales"}
    if missing := required - set(frame.columns):
        raise ValueError(f"training panel is missing columns: {sorted(missing)}")
    train_end = pd.Timestamp(config.train_end_date)
    validation_start = pd.Timestamp(config.validation_start_date)
    validation_end = pd.Timestamp(config.validation_end_date)
    if validation_start != train_end + _days(1) or validation_end < validation_start:
        raise ValueError("validation boundary must immediately follow train_end_date")
    if (validation_end - validation_start).days + 1 != config.horizon_days:
        raise ValueError("validation date range must equal horizon_days")

    panel = frame.sort_values(["store_nbr", "family", "date"]).reset_index(drop=True)
    if panel.duplicated(["store_nbr", "family", "date"]).any():
        raise ValueError("panel key/date rows must be unique")
    if (panel["sales"] < 0).any():
        raise ValueError("sales must be nonnegative")
    train = panel.loc[panel["date"] <= train_end].copy()
    validation = panel.loc[(panel["date"] >= validation_start) & (panel["date"] <= validation_end)].copy()
    if validation.empty:
        raise ValueError("frozen validation rows are unavailable")

    lookup = _sales_lookup(train)
    predictions: list[pd.DataFrame] = []
    lineage: list[dict[str, object]] = []
    for horizon in range(1, config.horizon_days + 1):
        target_date = train_end + _days(horizon)
        target = validation.loc[validation["date"] == target_date].copy()
        if target.empty:
            raise ValueError(f"missing validation rows for horizon {horizon}")
        fit = _build_training_rows(train, lookup, target_date, config, horizon)
        feature_columns = ["lag_1", "lag_7", "lag_14", "lag_28", "lag_mean_7", "horizon"]
        probability, magnitude = _fit_predict(fit, target, lookup, feature_columns, config, horizon)
        output = target[["date", "store_nbr", "family", "sales"]].copy()
        output["horizon"] = horizon
        output["probability_positive"] = probability
        output["conditional_log1p_sales"] = magnitude
        output["prediction"] = np.maximum(0.0, probability * np.expm1(magnitude))
        predictions.append(output)
        lineage.append(
            {
                "horizon": horizon,
                "target_date": target_date.date().isoformat(),
                "feature_max_source_date": (target_date - _days(1)).date().isoformat(),
                "past_only": True,
                "features": feature_columns,
            }
        )

    values = pd.concat(predictions, ignore_index=True)
    evaluation = _evaluation(values)
    prediction_path = context.workdir / "validation-predictions.csv"
    evaluation_path = context.workdir / "evaluation.json"
    lineage_path = context.workdir / "feature-lineage.json"
    values.to_csv(prediction_path, index=False)
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True), encoding="utf-8")
    lineage_path.write_text(json.dumps({"horizons": lineage}, indent=2, sort_keys=True), encoding="utf-8")
    return ComponentRunOutput(
        outputs={
            "validation_predictions": prediction_path,
            "evaluation": evaluation_path,
            "feature_lineage": lineage_path,
        },
        metrics={"rmsle": evaluation["rmsle"], "validation_rows": len(values)},
    )


def _sales_lookup(frame: pd.DataFrame) -> dict[tuple[int, str, pd.Timestamp], float]:
    return {
        (int(row.store_nbr), str(row.family), pd.Timestamp(row.date)): float(row.sales)
        for row in frame[["store_nbr", "family", "date", "sales"]].itertuples(index=False)
    }


def _days(value: int) -> pd.DateOffset:
    return pd.DateOffset(days=int(value))


def _feature_row(store: int, family: str, date: pd.Timestamp, lookup: dict[tuple[int, str, pd.Timestamp], float], horizon: int) -> dict[str, float]:
    lag = lambda days: lookup.get((store, family, date - _days(days)), 0.0)
    recent = [lag(days) for days in range(1, 8)]
    return {"lag_1": lag(1), "lag_7": lag(7), "lag_14": lag(14), "lag_28": lag(28), "lag_mean_7": float(np.mean(recent)), "horizon": float(horizon)}


def _build_training_rows(train: pd.DataFrame, lookup: dict[tuple[int, str, pd.Timestamp], float], target_date: pd.Timestamp, config: MercuryHurdlePanelConfig, horizon: int) -> pd.DataFrame:
    train_end = train["date"].max()
    earliest = train_end - _days(config.training_window_days)
    eligible = train.loc[
        (train["date"] >= earliest)
        & (train["date"] <= train_end - _days(horizon))
    ]
    sampled = eligible.sample(n=min(len(eligible), config.max_rows_per_horizon), random_state=horizon)
    rows: list[dict[str, float]] = []
    for row in sampled.itertuples(index=False):
        feature_date = pd.Timestamp(row.date)
        label_date = feature_date + _days(horizon)
        label = lookup.get((int(row.store_nbr), str(row.family), label_date))
        if label is None:
            continue
        values = _feature_row(int(row.store_nbr), str(row.family), feature_date, lookup, horizon)
        values["sales"] = label
        rows.append(values)
    result = pd.DataFrame(rows)
    if len(result) < 50 or result["sales"].nunique() < 2:
        raise ValueError("insufficient diverse past-only training rows for hurdle model")
    return result


def _fit_predict(fit: pd.DataFrame, target: pd.DataFrame, lookup: dict[tuple[int, str, pd.Timestamp], float], features: list[str], config: MercuryHurdlePanelConfig, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    target_features = pd.DataFrame([_feature_row(int(row.store_nbr), str(row.family), pd.Timestamp(row.date), lookup, horizon) for row in target.itertuples(index=False)])
    positive = (fit["sales"] > 0).astype(int)
    classifier = HistGradientBoostingClassifier(max_iter=config.max_iter, learning_rate=config.learning_rate, max_leaf_nodes=config.max_leaf_nodes, l2_regularization=config.l2_regularization, random_state=horizon)
    classifier.fit(fit[features], positive)
    probability = classifier.predict_proba(target_features[features])[:, 1]
    positive_fit = fit.loc[positive == 1]
    if len(positive_fit) < 25:
        raise ValueError("insufficient positive rows for conditional magnitude model")
    regressor = HistGradientBoostingRegressor(max_iter=config.max_iter, learning_rate=config.learning_rate, max_leaf_nodes=config.max_leaf_nodes, l2_regularization=config.l2_regularization, random_state=horizon)
    regressor.fit(positive_fit[features], np.log1p(positive_fit["sales"]))
    return probability, regressor.predict(target_features[features])


def _evaluation(values: pd.DataFrame) -> dict[str, float | int]:
    actual = values["sales"].to_numpy()
    predicted = values["prediction"].to_numpy()
    result: dict[str, float | int] = {"rmsle": float(mean_squared_log_error(actual, predicted) ** 0.5), "validation_rows": len(values), "zero_target_rows": int((actual == 0).sum()), "positive_target_rows": int((actual > 0).sum())}
    for name, mask in {"zero": actual == 0, "positive": actual > 0}.items():
        if mask.any():
            result[f"{name}_rmsle"] = float(mean_squared_log_error(actual[mask], predicted[mask]) ** 0.5)
    return result
