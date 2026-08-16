"""A deterministic, past-only seasonal-naive panel forecasting baseline."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from services.isolation import BenchmarkIsolationError, IsolationProfile
from services.tools.runner import ToolContext, ToolOutput

_REQUIRED_COLUMNS = ("date", "store_nbr", "family", "sales")

#: Mirrors ``ToolOutput.metrics``.  Scored metrics and the run descriptors
#: recorded alongside them share one record, so the record's type is the union
#: rather than the float type of the scores alone.
MetricValue = float | int | str | bool | None


def run_seasonal_naive_baseline(context: ToolContext) -> ToolOutput:
    """Forecast a chronological holdout using only observations before its cutoff.

    The handler accepts one labeled local CSV and uses its holdout labels solely
    in the evaluator after forecasting. It never updates history with holdout
    labels, so multi-day holdouts cannot leak future targets into predictions.
    """

    config = context.parameters
    _require_protected_profile(config)
    source = _allowed_file(config, "train_path", read=True)
    output_dir = _allowed_directory(config, "output_dir", write=True)
    forecast_path = config.get("forecast_path")
    if isinstance(forecast_path, str):
        forecast = _allowed_file(config, "forecast_path", read=True)
        return _forecast_unlabeled_panel(config, source, forecast, output_dir)
    holdout_start = _parse_date(config.get("holdout_start_date"), "holdout_start_date")
    holdout_end = _parse_date(config.get("holdout_end_date"), "holdout_end_date")
    if holdout_end < holdout_start:
        raise ValueError("holdout_end_date must be on or after holdout_start_date")
    lag_days = int(config.get("seasonal_lag_days", 7))
    if lag_days <= 0:
        raise ValueError("seasonal_lag_days must be positive")

    rows = _read_rows(source)
    _validate_rows(rows)
    history, holdout = _partition_rows(rows, holdout_start, holdout_end)
    if not history or not holdout:
        raise ValueError("both pre-holdout training rows and holdout rows are required")
    recursive = bool(config.get("recursive_seasonal", False))
    predictions, fallback_counts = _forecast(history, holdout, lag_days, recursive=recursive)
    metrics: dict[str, MetricValue] = dict(_metrics(holdout, predictions))
    metrics.update(
        {
            "row_count": len(holdout),
            "holdout_start_date": holdout_start.isoformat(),
            "holdout_end_date": holdout_end.isoformat(),
            "seasonal_lag_days": lag_days,
            "recursive_seasonal": recursive,
            **fallback_counts,
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "validation_predictions.csv"
    metrics_path = output_dir / "metrics.json"
    _write_predictions(predictions_path, holdout, predictions)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return ToolOutput(
        output_refs=[str(predictions_path), str(metrics_path)],
        artifact_refs=[str(predictions_path), str(metrics_path)],
        metrics=metrics,
    )


def _forecast_unlabeled_panel(
    config: dict[str, Any], source: Path, forecast_path: Path, output_dir: Path
) -> ToolOutput:
    lag_days = int(config.get("seasonal_lag_days", 7))
    if lag_days <= 0:
        raise ValueError("seasonal_lag_days must be positive")
    history = _read_rows(source)
    forecast = _read_rows(forecast_path)
    _validate_rows(history)
    _validate_forecast_rows(forecast)
    if not forecast:
        raise ValueError("forecast panel must contain rows")
    train_end = max(_parse_date(row["date"], "date") for row in history)
    if any(_parse_date(row["date"], "date") <= train_end for row in forecast):
        raise ValueError("forecast dates must be strictly after training history")
    recursive = bool(config.get("recursive_seasonal", False))
    predictions, fallback_counts = _forecast(history, forecast, lag_days, recursive=recursive)
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "submission.csv"
    _write_submission(predictions_path, forecast, predictions)
    metadata_path = output_dir / "test_forecast_metadata.json"
    metadata: dict[str, MetricValue] = {
        "row_count": len(forecast),
        "train_end_date": train_end.isoformat(),
        "seasonal_lag_days": lag_days,
        "recursive_seasonal": recursive,
        **fallback_counts,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return ToolOutput(
        output_refs=[str(predictions_path), str(metadata_path)],
        artifact_refs=[str(predictions_path), str(metadata_path)],
        metrics=metadata,
    )


def _allowed_file(config: dict[str, Any], name: str, *, read: bool) -> Path:
    value = config.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty path")
    path = Path(value).resolve()
    _require_allowlisted(path, config, read=read)
    if not path.is_file():
        raise ValueError(f"{name} must be an existing file")
    return path


def _allowed_directory(config: dict[str, Any], name: str, *, write: bool) -> Path:
    value = config.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty path")
    path = Path(value).resolve()
    _require_allowlisted(path, config, read=not write)
    return path


def _require_allowlisted(path: Path, config: dict[str, Any], *, read: bool) -> None:
    profile = _require_protected_profile(config)
    roots = profile.allowed_read_paths if read else profile.allowed_write_paths
    if not roots:
        raise BenchmarkIsolationError("protected benchmark requires declared path allowlists")
    resolved_roots = [Path(root).resolve() for root in roots]
    if not any(path == root or root in path.parents for root in resolved_roots):
        mode = "read" if read else "write"
        raise BenchmarkIsolationError(f"{mode} path is outside benchmark allowlist: {path}")


def _require_protected_profile(config: dict[str, Any]) -> IsolationProfile:
    """This trusted baseline is benchmark-only and never has an open mode."""
    if config.get("benchmark_protected") is not True:
        raise BenchmarkIsolationError("seasonal-naive baseline requires benchmark protection")
    profile = config.get("isolation_profile")
    if not isinstance(profile, IsolationProfile):
        raise BenchmarkIsolationError("protected benchmark requires an isolation profile")
    deny_all = (
        profile.network == "deny_all"
        and profile.subprocess == "deny"
        and profile.external_provider == "deny"
    )
    if not deny_all:
        raise BenchmarkIsolationError(
            "seasonal-naive baseline requires a deny-all isolation profile"
        )
    return profile


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _validate_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("training panel must contain rows")
    missing = [column for column in _REQUIRED_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError(f"training panel missing columns: {missing}")
    seen: set[tuple[date, str, str]] = set()
    for row in rows:
        current = _parse_date(row.get("date"), "date")
        key = (current, row.get("store_nbr", ""), row.get("family", ""))
        if not key[1] or not key[2]:
            raise ValueError("panel key values must be non-empty")
        if key in seen:
            raise ValueError("training panel contains duplicate date/store_nbr/family keys")
        seen.add(key)
        try:
            sales = float(row["sales"])
        except (TypeError, ValueError) as exc:
            raise ValueError("sales must be numeric") from exc
        if not math.isfinite(sales) or sales < 0:
            raise ValueError("sales must be finite and nonnegative")


def _validate_forecast_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("forecast panel must contain rows")
    required = ("id", "date", "store_nbr", "family")
    missing = [column for column in required if column not in rows[0]]
    if missing:
        raise ValueError(f"forecast panel missing columns: {missing}")
    if "sales" in rows[0]:
        raise ValueError("forecast panel must not contain sales")
    seen: set[tuple[date, str, str]] = set()
    ids: set[str] = set()
    for row in rows:
        current = _parse_date(row.get("date"), "date")
        key = (current, row.get("store_nbr", ""), row.get("family", ""))
        if not key[1] or not key[2] or not row.get("id"):
            raise ValueError("forecast identifiers and panel key values must be non-empty")
        if key in seen or row["id"] in ids:
            raise ValueError("forecast panel contains duplicate identifiers or panel keys")
        seen.add(key)
        ids.add(row["id"])


def _partition_rows(
    rows: list[dict[str, str]], holdout_start: date, holdout_end: date
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    history, holdout = [], []
    for row in rows:
        current = _parse_date(row["date"], "date")
        if current < holdout_start:
            history.append(row)
        elif current <= holdout_end:
            holdout.append(row)
    if any(_parse_date(row["date"], "date") >= holdout_start for row in history):
        raise ValueError("chronological partition failed")
    return history, holdout


def _forecast(
    history: list[dict[str, str]],
    holdout: list[dict[str, str]],
    lag_days: int,
    *,
    recursive: bool,
) -> tuple[list[float], dict[str, int]]:
    series: dict[tuple[str, str], dict[date, float]] = defaultdict(dict)
    for row in history:
        key = (row["store_nbr"], row["family"])
        series[key][_parse_date(row["date"], "date")] = float(row["sales"])
    predictions: list[float] = []
    seasonal, fallback, cold_start = 0, 0, 0
    for row in holdout:
        current = _parse_date(row["date"], "date")
        values = series[(row["store_nbr"], row["family"])]
        seasonal_value = values.get(current - timedelta(days=lag_days))
        if seasonal_value is not None:
            prediction, seasonal = seasonal_value, seasonal + 1
        else:
            previous = [observed for observed in values if observed < current]
            if previous:
                prediction, fallback = values[max(previous)], fallback + 1
            else:
                prediction, cold_start = 0.0, cold_start + 1
        prediction = max(0.0, prediction)
        predictions.append(prediction)
        if recursive:
            values[current] = prediction
    return predictions, {
        "seasonal_lag_count": seasonal,
        "last_observed_fallback_count": fallback,
        "cold_start_zero_count": cold_start,
        "zero_clipping_count": 0,
    }


def _metrics(holdout: list[dict[str, str]], predictions: list[float]) -> dict[str, float]:
    actual = [float(row["sales"]) for row in holdout]
    pairs = list(zip(actual, predictions, strict=True))
    absolute = [abs(observed - predicted) for observed, predicted in pairs]
    squared = [(observed - predicted) ** 2 for observed, predicted in pairs]
    log_squared = [
        (math.log1p(observed) - math.log1p(predicted)) ** 2 for observed, predicted in pairs
    ]
    total_actual = sum(actual)
    return {
        "rmsle": math.sqrt(sum(log_squared) / len(log_squared)),
        "mae": sum(absolute) / len(absolute),
        "rmse": math.sqrt(sum(squared) / len(squared)),
        "wape": sum(absolute) / total_actual if total_actual else 0.0,
    }


def _write_predictions(path: Path, holdout: list[dict[str, str]], predictions: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["date", "store_nbr", "family", "sales_prediction"]
        )
        writer.writeheader()
        for row, prediction in zip(holdout, predictions, strict=True):
            writer.writerow(
                {
                    "date": row["date"],
                    "store_nbr": row["store_nbr"],
                    "family": row["family"],
                    "sales_prediction": prediction,
                }
            )


def _write_submission(path: Path, forecast: list[dict[str, str]], predictions: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "sales"])
        writer.writeheader()
        for row, prediction in zip(forecast, predictions, strict=True):
            writer.writerow({"id": row["id"], "sales": prediction})


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
