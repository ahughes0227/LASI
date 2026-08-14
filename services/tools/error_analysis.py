"""Deterministic error bucketing for tabular and time-series predictions."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .runner import ToolContext, ToolOutput


def run_error_analysis(context: ToolContext) -> ToolOutput:
    """Analyze row-level predictions and emit a structured, reviewable artifact.

    The approved plan supplies a CSV containing actual and predicted values.
    Optional segment columns expose concentrated failures; a comparator column
    shows where a candidate regresses against the protected baseline.
    """
    source = Path(_required_string(context.parameters, "predictions_path")).resolve()
    output = Path(_required_string(context.parameters, "output_path")).resolve()
    actual_column = str(context.parameters.get("actual_column", "actual"))
    prediction_column = str(context.parameters.get("prediction_column", "prediction"))
    comparator_column = context.parameters.get("comparator_column")
    segment_columns = context.parameters.get("segment_columns", [])
    if not isinstance(segment_columns, list) or not all(
        isinstance(item, str) for item in segment_columns
    ):
        raise ValueError("segment_columns must be a list of column names")

    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("prediction file contains no rows")
    required = {actual_column, prediction_column, *segment_columns}
    missing = sorted(required - set(rows[0]))
    if missing:
        raise ValueError(f"prediction file is missing columns: {', '.join(missing)}")

    analyzed: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        actual = _number(row[actual_column], actual_column, index)
        prediction = _number(row[prediction_column], prediction_column, index)
        squared_log_error = _squared_log_error(actual, prediction)
        item: dict[str, Any] = {
            "actual": actual,
            "prediction": prediction,
            "squared_log_error": squared_log_error,
            "absolute_error": abs(prediction - actual),
            "segments": {column: row[column] for column in segment_columns},
        }
        if isinstance(comparator_column, str):
            if comparator_column not in row:
                raise ValueError(f"prediction file is missing column: {comparator_column}")
            comparator = _number(row[comparator_column], comparator_column, index)
            item["comparator_squared_log_error"] = _squared_log_error(actual, comparator)
        analyzed.append(item)

    total_sle = sum(item["squared_log_error"] for item in analyzed)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "tool_run_id": context.tool_run_id,
        "project_id": context.project_id,
        "dataset_version_id": context.dataset_version_id,
        "row_count": len(analyzed),
        "overall": {
            "rmsle": math.sqrt(total_sle / len(analyzed)),
            "mean_absolute_error": sum(item["absolute_error"] for item in analyzed) / len(analyzed),
        },
        "target_regimes": _target_regimes(analyzed, total_sle),
        "segments": {column: _segment_summary(analyzed, column) for column in segment_columns},
        "worst_rows": sorted(
            (
                {
                    "row_index": index,
                    "actual": item["actual"],
                    "prediction": item["prediction"],
                    "squared_log_error": item["squared_log_error"],
                    "segments": item["segments"],
                }
                for index, item in enumerate(analyzed)
            ),
            key=lambda item: item["squared_log_error"],
            reverse=True,
        )[:20],
    }
    if isinstance(comparator_column, str):
        improved = sum(
            item["squared_log_error"] < item["comparator_squared_log_error"] for item in analyzed
        )
        report["comparator"] = {
            "column": comparator_column,
            "candidate_better_row_fraction": improved / len(analyzed),
            "candidate_rmsle": report["overall"]["rmsle"],
            "comparator_rmsle": math.sqrt(
                sum(item["comparator_squared_log_error"] for item in analyzed) / len(analyzed)
            ),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ToolOutput(
        output_refs=[str(output)],
        artifact_refs=[str(output)],
        metrics={
            "row_count": len(analyzed),
            "rmsle": report["overall"]["rmsle"],
            "zero_target_error_share": report["target_regimes"]["zero"]["error_share"],
        },
    )


def _target_regimes(rows: list[dict[str, Any]], total_sle: float) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, subset in {
        "zero": [item for item in rows if item["actual"] == 0],
        "positive": [item for item in rows if item["actual"] > 0],
    }.items():
        sle = sum(item["squared_log_error"] for item in subset)
        result[name] = {
            "row_count": len(subset),
            "row_fraction": len(subset) / len(rows),
            "error_share": sle / total_sle if total_sle else 0.0,
            "rmsle": math.sqrt(sle / len(subset)) if subset else None,
        }
    return result


def _segment_summary(rows: list[dict[str, Any]], column: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        groups[str(item["segments"][column])].append(item)
    summaries = []
    for value, items in groups.items():
        sle = sum(item["squared_log_error"] for item in items)
        summaries.append(
            {
                "value": value,
                "row_count": len(items),
                "rmsle": math.sqrt(sle / len(items)),
                "error_share": sle / sum(row["squared_log_error"] for row in rows)
                if any(row["squared_log_error"] for row in rows)
                else 0.0,
            }
        )
    return sorted(summaries, key=lambda item: item["rmsle"], reverse=True)


def _squared_log_error(actual: float, prediction: float) -> float:
    if actual < 0:
        raise ValueError("RMSLE error analysis does not allow negative actual values")
    return (math.log1p(max(0.0, prediction)) - math.log1p(actual)) ** 2


def _required_string(parameters: dict[str, Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"parameters.{name} must be a non-empty path")
    return value


def _number(value: Any, column: str, row_index: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_index} column {column} is not numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_index} column {column} is not finite")
    return number
