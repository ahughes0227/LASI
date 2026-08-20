"""Small deterministic model floors for the clean-room benchmark suite."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Literal

import pandas as pd
from pydantic import Field
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from services.contracts.models import StrictModel


class ReferenceBaselineResult(StrictModel):
    benchmark_id: str
    metric: str
    direction: Literal["maximize", "minimize"]
    value: float
    train_rows: int = Field(gt=0)
    validation_rows: int = Field(gt=0)
    wall_clock_seconds: float = Field(gt=0)
    token_usage: Literal["not_applicable"] = "not_applicable"
    prior_run_refs: list[str] = Field(default_factory=list, max_length=0)


def run_titanic_reference(train_path: Path, validation_path: Path) -> ReferenceBaselineResult:
    start = perf_counter()
    train = pd.read_csv(train_path)
    validation = pd.read_csv(validation_path)
    numeric = ["Pclass", "Age", "SibSp", "Parch", "Fare"]
    categorical = ["Sex", "Embarked"]
    features = numeric + categorical
    model = Pipeline(
        [
            (
                "preprocess",
                ColumnTransformer(
                    [
                        (
                            "numeric",
                            Pipeline(
                                [
                                    ("impute", SimpleImputer(strategy="median")),
                                    ("scale", StandardScaler()),
                                ]
                            ),
                            numeric,
                        ),
                        (
                            "categorical",
                            Pipeline(
                                [
                                    ("impute", SimpleImputer(strategy="most_frequent")),
                                    ("encode", OneHotEncoder(handle_unknown="ignore")),
                                ]
                            ),
                            categorical,
                        ),
                    ]
                ),
            ),
            ("model", LogisticRegression(max_iter=1000, random_state=20260820)),
        ]
    )
    model.fit(train[features], train["Survived"])
    predictions = model.predict(validation[features])
    return ReferenceBaselineResult(
        benchmark_id="titanic-cleanroom-v1",
        metric="accuracy",
        direction="maximize",
        value=float(accuracy_score(validation["Survived"], predictions)),
        train_rows=len(train),
        validation_rows=len(validation),
        wall_clock_seconds=perf_counter() - start,
    )


def run_pjme_reference(train_path: Path, validation_path: Path) -> ReferenceBaselineResult:
    start = perf_counter()
    train = pd.read_csv(train_path, parse_dates=["Datetime"]).sort_values("Datetime", kind="stable")
    validation = pd.read_csv(validation_path, parse_dates=["Datetime"]).sort_values(
        "Datetime", kind="stable"
    )
    history = dict(zip(train["Datetime"], train["PJME_MW"], strict=True))
    predictions: list[float] = []
    for timestamp in validation["Datetime"]:
        seasonal_timestamp = timestamp - pd.Timedelta(hours=168)
        if seasonal_timestamp not in history:
            raise ValueError(f"missing seasonal history for {timestamp}")
        prediction = float(history[seasonal_timestamp])
        predictions.append(prediction)
        history[timestamp] = prediction
    return ReferenceBaselineResult(
        benchmark_id="pjme-hourly-cleanroom-v1",
        metric="mean_absolute_error",
        direction="minimize",
        value=float(mean_absolute_error(validation["PJME_MW"], predictions)),
        train_rows=len(train),
        validation_rows=len(validation),
        wall_clock_seconds=perf_counter() - start,
    )


def run_digit_reference(train_path: Path, validation_path: Path) -> ReferenceBaselineResult:
    start = perf_counter()
    train = pd.read_csv(train_path)
    validation = pd.read_csv(validation_path)
    features = [column for column in train if column.startswith("pixel")]
    model = SGDClassifier(
        loss="log_loss",
        alpha=0.0001,
        max_iter=50,
        tol=0.001,
        random_state=20260820,
    )
    model.fit(train[features].to_numpy(dtype="float32") / 255, train["label"])
    predictions = model.predict(validation[features].to_numpy(dtype="float32") / 255)
    return ReferenceBaselineResult(
        benchmark_id="digit-recognizer-cleanroom-v1",
        metric="accuracy",
        direction="maximize",
        value=float(accuracy_score(validation["label"], predictions)),
        train_rows=len(train),
        validation_rows=len(validation),
        wall_clock_seconds=perf_counter() - start,
    )
