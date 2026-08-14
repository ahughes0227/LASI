"""Small deterministic tabular baselines; sklearn objects never cross the LASI contract boundary."""
from __future__ import annotations

# fmt: off

import csv
import json
import platform
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

# ruff: noqa: I001
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from services.datasets.leakage import audit_tabular
from services.tools.runner import ToolContext, ToolOutput

# ruff: noqa: E501, I001


def run_tabular_baseline(context: ToolContext) -> ToolOutput:
    """Run only from the registered tool runner after a matching decision."""
    config = context.parameters
    train_path = Path(str(config["train_path"])).resolve()
    test_path = Path(str(config["test_path"])).resolve()
    target = str(config["target_column"])
    split = str(config.get("split_column", "split"))
    problem_type = str(config["problem_type"])
    seed = int(config.get("seed", 0))
    train = _read_csv(train_path)
    test = _read_csv(test_path)
    if not train or not test:
        raise ValueError("train and test files must contain rows")
    if target not in train[0] or target in test[0]:
        raise ValueError("target must exist only in training data")
    if split in train[0] and len({row.get(split) for row in train}) < 1:
        raise ValueError("invalid split column")
    features = list(config.get("feature_columns", [name for name in train[0] if name not in {target, split}]))
    missing = [name for name in features if name not in train[0] or name not in test[0]]
    if missing:
        raise ValueError(f"missing feature columns: {missing}")
    audit = audit_tabular(train, test, target_columns=[target], identifier_columns=list(config.get("identifier_columns", [])))
    if audit.blocking:
        raise ValueError("leakage audit blocked baseline: " + "; ".join(item.message for item in audit.findings if item.severity == "block"))
    validation = train
    if split in train[0] and any(row.get(split) == "validation" for row in train):
        fitting = [row for row in train if row.get(split) == "train"]
        validation = [row for row in train if row.get(split) == "validation"]
    else:
        fitting = train
    if not fitting or not validation:
        raise ValueError("train and validation rows are required; no implicit split is created")
    numeric = [name for name in features if _is_numeric(fitting, name)]
    categorical = [name for name in features if name not in numeric]
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    model = LogisticRegression(random_state=seed, max_iter=1000, solver="liblinear") if problem_type == "classification" else Ridge(alpha=1.0)
    if problem_type not in {"classification", "regression"}:
        raise ValueError(f"unsupported baseline problem type: {problem_type}")
    pipeline = Pipeline([("preprocess", preprocessor), ("model", model)])
    x_fit, y_fit = pd.DataFrame(_matrix(fitting, features), columns=features), [row[target] for row in fitting]
    x_val, y_val = pd.DataFrame(_matrix(validation, features), columns=features), [row[target] for row in validation]
    pipeline.fit(x_fit, y_fit)
    predictions = pipeline.predict(x_val)
    metrics = _metrics(problem_type, y_val, predictions)
    output_dir = Path(str(config.get("output_dir", train_path.parent / "artifacts"))).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pred_path = output_dir / "validation_predictions.csv"
    _write_predictions(pred_path, validation, predictions, config.get("identifier_columns", []), target)
    # Model selection is complete; the final model is fit on all approved labels
    # and then applied once to the unlabeled test source.
    pipeline.fit(_matrix_frame(train, features), [row[target] for row in train])
    test_predictions = pipeline.predict(_matrix_frame(test, features))
    test_pred_path = output_dir / "test_predictions.csv"
    _write_predictions(test_pred_path, test, test_predictions, config.get("identifier_columns", []), target)
    metadata = output_dir / "baseline_metadata.json"
    metadata.write_text(json.dumps({"model": model.__class__.__name__, "features": features, "seed": seed,
                                    "split": {"fit": len(fitting), "validation": len(validation)},
                                    "metrics": metrics, "python": sys.version, "platform": platform.platform()}, sort_keys=True, indent=2), encoding="utf-8")
    refs = [str(pred_path), str(test_pred_path), str(metadata)]
    return ToolOutput(output_refs=refs, artifact_refs=refs, metrics=metrics,
                      warnings=[finding.message for finding in audit.findings if finding.severity != "block"])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _is_numeric(rows: list[dict[str, Any]], column: str) -> bool:
    values = [row.get(column) for row in rows if row.get(column) not in (None, "")]
    if not values:
        return True
    try:
        [float(str(value)) for value in values]
    except (TypeError, ValueError):
        return False
    return True


def _matrix(rows: list[dict[str, Any]], features: list[str]) -> list[list[Any]]:
    return [[float(row[name]) if row[name] not in (None, "") and _number(row[name]) else row[name] for name in features] for row in rows]


def _matrix_frame(rows: list[dict[str, Any]], features: list[str]) -> pd.DataFrame:
    return pd.DataFrame(_matrix(rows, features), columns=features)


def _number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _metrics(problem_type: str, actual: list[Any], predicted: Any) -> dict[str, float | int | str | bool | None]:
    if problem_type == "classification":
        return {"accuracy": float(accuracy_score(actual, predicted)), "macro_f1": float(f1_score(actual, predicted, average="macro"))}
    return {"rmse": float(mean_squared_error(actual, predicted) ** 0.5), "mae": float(mean_absolute_error(actual, predicted)), "r2": float(r2_score(actual, predicted))}


def _write_predictions(path: Path, rows: list[dict[str, Any]], predictions: Any, ids: list[str], target: str) -> None:
    columns = [*ids, "prediction"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row, prediction in zip(rows, predictions, strict=True):
            writer.writerow({**{column: row[column] for column in ids}, "prediction": prediction.item() if hasattr(prediction, "item") else prediction})
