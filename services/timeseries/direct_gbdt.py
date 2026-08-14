"""Direct multi-horizon gradient-boosted retail panel forecasting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import HistGradientBoostingRegressor

from services.isolation import BenchmarkIsolationError, IsolationProfile
from services.tools.runner import ToolContext, ToolOutput


class DirectGbdtConfig(BaseModel):
    """Closed configuration for the trusted direct forecast branch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train_path: str
    output_dir: str
    forecast_path: str | None = None
    validation_start_date: str | None = None
    validation_end_date: str | None = None
    horizon_days: int = Field(default=16, ge=1, le=31)
    training_window_days: int = Field(default=730, ge=90, le=1460)
    max_rows_per_horizon: int = Field(default=30000, ge=1000, le=100000)
    max_iter: int = Field(default=120, ge=20, le=300)
    learning_rate: float = Field(default=0.08, gt=0, le=1)
    max_leaf_nodes: int = Field(default=31, ge=4, le=255)
    l2_regularization: float = Field(default=1.0, ge=0)
    seed: int = 20260813


def run_direct_horizon_gbdt(context: ToolContext) -> ToolOutput:
    """Fit one global horizon-conditioned model using only origin-available data."""

    raw = DirectGbdtConfig.model_validate(_serializable_config(context.parameters))
    _require_profile(context.parameters)
    train_path = _allowed_file(raw.train_path, context.parameters, read=True)
    output_dir = _allowed_directory(raw.output_dir, context.parameters)
    train = _load_train(train_path)
    if raw.forecast_path is not None:
        forecast_path = _allowed_file(raw.forecast_path, context.parameters, read=True)
        forecast = _load_forecast(forecast_path)
        cutoff = train["date"].max()
        if forecast["date"].min() <= cutoff:
            raise ValueError("forecast dates must be strictly after observed training dates")
        model, summary = _fit(train, cutoff, raw)
        predictions = _predict_test(model, train, forecast, cutoff, raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        submission = output_dir / "submission.csv"
        predictions.rename(columns={"prediction": "sales"}).to_csv(submission, index=False)
        metadata = output_dir / "metadata.json"
        metadata.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        return ToolOutput(
            output_refs=[str(submission), str(metadata)],
            artifact_refs=[str(submission), str(metadata)],
            metrics=summary,
        )
    if raw.validation_start_date is None or raw.validation_end_date is None:
        raise ValueError("validation dates are required when forecast_path is absent")
    start = pd.Timestamp(raw.validation_start_date)
    end = pd.Timestamp(raw.validation_end_date)
    if end < start:
        raise ValueError("validation end must not precede validation start")
    cutoff = start - pd.Timedelta(days=1)
    model, summary = _fit(train, cutoff, raw)
    validation = train[(train["date"] >= start) & (train["date"] <= end)].copy()
    predictions = _predict_test(model, train[train["date"] <= cutoff], validation, cutoff, raw)
    actual = validation.set_index("id")["sales"]
    joined = predictions.set_index("id").join(actual, how="inner")
    if len(joined) != len(validation):
        raise ValueError("validation prediction IDs do not exactly match labels")
    log_error = np.log1p(joined["sales"]) - np.log1p(joined["prediction"])
    rmsle = float(np.sqrt(np.mean(log_error**2)))
    summary.update({"rmsle": rmsle, "validation_rows": len(joined)})
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "validation_predictions.csv"
    joined.reset_index().to_csv(prediction_path, index=False)
    metadata = output_dir / "metrics.json"
    metadata.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return ToolOutput(
        output_refs=[str(prediction_path), str(metadata)],
        artifact_refs=[str(prediction_path), str(metadata)],
        metrics=summary,
    )


def _serializable_config(value: dict[str, Any]) -> dict[str, Any]:
    ignored = {"benchmark_protected", "isolation_profile", "isolation_backend", "tool_version"}
    return {key: item for key, item in value.items() if key not in ignored}


def _require_profile(config: dict[str, Any]) -> IsolationProfile:
    if config.get("benchmark_protected") is not True:
        raise BenchmarkIsolationError("direct GBDT requires benchmark protection")
    profile = config.get("isolation_profile")
    if not isinstance(profile, IsolationProfile):
        raise BenchmarkIsolationError("direct GBDT requires an isolation profile")
    if (
        profile.network != "deny_all"
        or profile.subprocess != "deny"
        or profile.external_provider != "deny"
        or not profile.benchmark_read_only
    ):
        raise BenchmarkIsolationError("direct GBDT requires a read-only deny-all profile")
    return profile


def _allowed_file(value: str, config: dict[str, Any], *, read: bool) -> Path:
    path = Path(value).resolve()
    profile = _require_profile(config)
    roots = profile.allowed_read_paths if read else profile.allowed_write_paths
    if not _inside_any(path, roots):
        raise BenchmarkIsolationError(f"path outside allowlist: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _allowed_directory(value: str, config: dict[str, Any]) -> Path:
    path = Path(value).resolve()
    profile = _require_profile(config)
    if not _inside_any(path, profile.allowed_write_paths):
        raise BenchmarkIsolationError(f"path outside write allowlist: {path}")
    return path


def _inside_any(path: Path, roots: tuple[str, ...]) -> bool:
    return any(
        path == Path(root).resolve() or Path(root).resolve() in path.parents for root in roots
    )


def _load_train(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"id", "date", "store_nbr", "family", "sales", "onpromotion"}
    if missing := required - set(frame.columns):
        raise ValueError(f"training data missing columns: {sorted(missing)}")
    if frame["id"].isna().any() or frame["id"].duplicated().any():
        raise ValueError("training data IDs must be non-null and unique")
    if frame.duplicated(["date", "store_nbr", "family"]).any():
        raise ValueError("training data contains duplicate panel keys")
    if (frame["sales"] < 0).any() or not np.isfinite(frame["sales"]).all():
        raise ValueError("sales must be finite and nonnegative")
    return frame.sort_values(["store_nbr", "family", "date"]).reset_index(drop=True)


def _load_forecast(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"id", "date", "store_nbr", "family", "onpromotion"}
    if missing := required - set(frame.columns):
        raise ValueError(f"forecast data missing columns: {sorted(missing)}")
    if frame["id"].isna().any() or frame["id"].duplicated().any():
        raise ValueError("forecast IDs must be non-null and unique")
    if "sales" in frame.columns or frame.duplicated(["date", "store_nbr", "family"]).any():
        raise ValueError("forecast data has target leakage or duplicate panel keys")
    return frame.sort_values(["store_nbr", "family", "date"]).reset_index(drop=True)


def _fit(
    train: pd.DataFrame, cutoff: pd.Timestamp, config: DirectGbdtConfig
) -> tuple[tuple[HistGradientBoostingRegressor, dict[str, int]], dict[str, Any]]:
    eligible = train[train["date"] < cutoff].copy()
    window_start = cutoff - pd.Timedelta(
        days=config.training_window_days + config.horizon_days
    )
    eligible = eligible[eligible["date"] >= window_start]
    examples = _examples(
        eligible, config.horizon_days, cutoff, config.max_rows_per_horizon, config.seed
    )
    if examples.empty:
        raise ValueError("no leakage-safe direct training examples")
    vocabulary = _family_vocabulary(examples)
    features = _feature_matrix(examples, vocabulary)
    model = HistGradientBoostingRegressor(
        learning_rate=config.learning_rate,
        max_iter=config.max_iter,
        max_leaf_nodes=config.max_leaf_nodes,
        l2_regularization=config.l2_regularization,
        random_state=config.seed,
    )
    model.fit(features, np.log1p(examples["target"].to_numpy(dtype=float)))
    return (model, vocabulary), {
        "training_rows": len(examples),
        "cutoff_date": cutoff.date().isoformat(),
        "horizon_days": config.horizon_days,
        "estimator": "HistGradientBoostingRegressor",
        "family_count": len(vocabulary),
    }


def _examples(
    train: pd.DataFrame, horizon: int, cutoff: pd.Timestamp, limit: int, seed: int
) -> pd.DataFrame:
    group = train.groupby(["store_nbr", "family"], sort=False)
    base = train.copy()
    base["lag_1"] = group["sales"].shift(1)
    base["lag_7"] = group["sales"].shift(7)
    base["lag_14"] = group["sales"].shift(14)
    base["lag_28"] = group["sales"].shift(28)
    base["roll_7"] = group["sales"].transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).mean()
    )
    rows: list[pd.DataFrame] = []
    for step in range(1, horizon + 1):
        value = base.copy()
        targets = train[["store_nbr", "family", "date", "sales", "onpromotion"]].copy()
        targets["date"] = targets["date"] - pd.Timedelta(days=step)
        targets = targets.rename(columns={"sales": "target", "onpromotion": "target_promotion"})
        value = value.merge(targets, on=["store_nbr", "family", "date"], how="left")
        value["horizon"] = step
        value["target_date"] = value["date"] + pd.Timedelta(days=step)
        value = value[
            (value["date"] < cutoff)
            & (value["target_date"] < cutoff)
            & value["target"].notna()
            & value["target_promotion"].notna()
        ]
        if len(value) > limit:
            value = value.sample(limit, random_state=seed + step)
        rows.append(value)
    return pd.concat(rows, ignore_index=True).dropna(
        subset=["lag_1", "lag_7", "lag_14", "lag_28", "roll_7"]
    )


def _predict_test(
    fitted: tuple[HistGradientBoostingRegressor, dict[str, int]],
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    cutoff: pd.Timestamp,
    config: DirectGbdtConfig,
) -> pd.DataFrame:
    model, vocabulary = fitted
    source = history.copy()
    group = source.groupby(["store_nbr", "family"], sort=False)
    source["lag_1"] = group["sales"].shift(1)
    source["lag_7"] = group["sales"].shift(7)
    source["lag_14"] = group["sales"].shift(14)
    source["lag_28"] = group["sales"].shift(28)
    source["roll_7"] = group["sales"].transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).mean()
    )
    origin = source[source["date"] == cutoff][
        ["store_nbr", "family", "lag_1", "lag_7", "lag_14", "lag_28", "roll_7"]
    ]
    result = forecast.merge(origin, on=["store_nbr", "family"], how="left", validate="many_to_one")
    result["horizon"] = (result["date"] - cutoff).dt.days
    result["target_promotion"] = result["onpromotion"]
    result["target_date"] = result["date"]
    invalid = (
        result["horizon"].lt(1).any()
        or result["horizon"].gt(config.horizon_days).any()
        or result.isna().any().any()
    )
    if invalid:
        raise ValueError("inference panel has invalid horizon or missing past-only feature")
    raw_prediction = model.predict(_feature_matrix(result, vocabulary))
    result["prediction"] = np.maximum(0.0, np.expm1(raw_prediction))
    output = result[["id", "prediction"]]
    if output["id"].isna().any() or output["id"].duplicated().any() or len(output) != len(forecast):
        raise ValueError("prediction output does not preserve unique forecast IDs")
    return output


def _family_vocabulary(frame: pd.DataFrame) -> dict[str, int]:
    return {family: index for index, family in enumerate(sorted(frame["family"].unique()))}


def _feature_matrix(frame: pd.DataFrame, vocabulary: dict[str, int]) -> np.ndarray:
    target_date = pd.to_datetime(frame["target_date"])
    family_codes = frame["family"].map(vocabulary)
    if family_codes.isna().any():
        raise ValueError("inference contains family absent from training vocabulary")
    columns = [
        frame["store_nbr"].to_numpy(dtype=float),
        family_codes.to_numpy(dtype=float),
        frame["horizon"].to_numpy(dtype=float),
        frame["target_promotion"].to_numpy(dtype=float),
        target_date.dt.dayofweek.to_numpy(dtype=float),
        target_date.dt.month.to_numpy(dtype=float),
        frame["lag_1"].to_numpy(dtype=float),
        frame["lag_7"].to_numpy(dtype=float),
        frame["lag_14"].to_numpy(dtype=float),
        frame["lag_28"].to_numpy(dtype=float),
        frame["roll_7"].to_numpy(dtype=float),
    ]
    return np.column_stack(columns)
