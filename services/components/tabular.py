"""Trusted, bounded components for baseline tabular classification experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from services.contracts import ComponentPort, ComponentSpec
from services.contracts.models import BudgetEstimate
from services.datasets.leakage import audit_tabular

from .execution import ComponentExecutionContext, ComponentRunOutput
from .registry import ComponentHandler, ComponentRegistry


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CsvDatasetConfig(_Config):
    train_path: str
    test_path: str
    target_column: str
    identifier_columns: list[str] = Field(default_factory=lambda: ["PassengerId"])
    feature_columns: list[str] = Field(default_factory=list)


class StratifiedHoldoutConfig(_Config):
    validation_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    seed: int = 42


class NaiveLogisticConfig(_Config):
    c: float = Field(default=1.0, gt=0)
    max_iter: int = Field(default=1000, ge=100)


class TitanicTitleFamilyConfig(_Config):
    """Fixed, reviewed Titanic feature family; intentionally not an open-ended DSL."""

    feature_set: Literal["title_family_v1"] = "title_family_v1"


class ClassificationEvaluatorConfig(_Config):
    primary_metric: Literal["accuracy", "macro_f1", "roc_auc"] = "accuracy"


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return [str(item) for item in value]


def _int_list(value: object, *, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return [int(item) for item in value]


def load_csv_dataset(context: ComponentExecutionContext) -> ComponentRunOutput:
    config: CsvDatasetConfig = context.config
    train = Path(config.train_path).resolve()
    test = Path(config.test_path).resolve()
    if not train.is_file() or not test.is_file():
        raise FileNotFoundError("tabular train and test CSV inputs must exist")
    train_columns = list(pd.read_csv(train, nrows=1).columns)
    test_columns = list(pd.read_csv(test, nrows=1).columns)
    if config.target_column not in train_columns or config.target_column in test_columns:
        raise ValueError("target must occur in train only")
    features = config.feature_columns or [
        column
        for column in train_columns
        if column not in {config.target_column, *config.identifier_columns}
    ]
    if not features or any(column not in test_columns for column in features):
        raise ValueError("feature columns must be non-empty and available in train and test")
    audit = audit_tabular(
        pd.read_csv(train).to_dict("records"),
        pd.read_csv(test).to_dict("records"),
        target_columns=[config.target_column],
        identifier_columns=config.identifier_columns,
    )
    if audit.blocking:
        raise ValueError(
            "leakage audit blocked dataset: " + "; ".join(item.message for item in audit.findings)
        )
    manifest = _write_json(
        context.workdir / "tabular-dataset.json",
        {
            "train_path": str(train),
            "test_path": str(test),
            "target_column": config.target_column,
            "identifier_columns": config.identifier_columns,
            "feature_columns": features,
        },
    )
    return ComponentRunOutput(
        outputs={"dataset": manifest}, warnings=[item.message for item in audit.findings]
    )


def stratified_holdout(context: ComponentExecutionContext) -> ComponentRunOutput:
    config: StratifiedHoldoutConfig = context.config
    dataset = _load_json(context.inputs["dataset"])
    train = pd.read_csv(str(dataset["train_path"]))
    target = str(dataset["target_column"])
    indices = list(range(len(train)))
    _, validation = train_test_split(
        indices,
        test_size=config.validation_fraction,
        random_state=config.seed,
        stratify=train[target],
    )
    split = _write_json(
        context.workdir / "holdout-split.json", {"validation_indices": sorted(validation)}
    )
    return ComponentRunOutput(
        outputs={"split": split}, metrics={"validation_rows": len(validation)}
    )


def titanic_title_family_features(context: ComponentExecutionContext) -> ComponentRunOutput:
    """Derive a small, established Titanic representation without changing source data."""
    dataset = _load_json(context.inputs["dataset"])
    target = str(dataset["target_column"])
    identifiers = _string_list(dataset["identifier_columns"], field="identifier_columns")
    train = _titanic_features(pd.read_csv(str(dataset["train_path"])))
    test = _titanic_features(pd.read_csv(str(dataset["test_path"])))
    features = [
        "Pclass",
        "Sex",
        "Age",
        "Fare",
        "Embarked",
        "Title",
        "FamilySize",
        "IsAlone",
    ]
    required = [*identifiers, target, "Name", "SibSp", "Parch", *features]
    missing = [column for column in required if column not in train.columns]
    if missing:
        raise ValueError(f"Titanic feature component requires columns: {missing}")
    train_path = context.workdir / "engineered-train.csv"
    test_path = context.workdir / "engineered-test.csv"
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    manifest = _write_json(
        context.workdir / "engineered-titanic-dataset.json",
        {
            "train_path": str(train_path),
            "test_path": str(test_path),
            "target_column": target,
            "identifier_columns": identifiers,
            "feature_columns": features,
            "feature_set": context.config.feature_set,
        },
    )
    return ComponentRunOutput(outputs={"dataset": manifest})


def _titanic_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if (
        "Name" not in result.columns
        or "SibSp" not in result.columns
        or "Parch" not in result.columns
    ):
        raise ValueError("Titanic source is missing Name, SibSp, or Parch")
    titles = result["Name"].str.extract(r",\s*([^.]*)\.", expand=False).fillna("Unknown")
    result["Title"] = titles.where(titles.isin({"Mr", "Miss", "Mrs", "Master"}), "Rare")
    result["FamilySize"] = result["SibSp"] + result["Parch"] + 1
    result["IsAlone"] = (result["FamilySize"] == 1).astype(int)
    return result


def naive_logistic_classifier(context: ComponentExecutionContext) -> ComponentRunOutput:
    config: NaiveLogisticConfig = context.config
    dataset = _load_json(context.inputs["dataset"])
    split = _load_json(context.inputs["split"])
    train = pd.read_csv(str(dataset["train_path"]))
    test = pd.read_csv(str(dataset["test_path"]))
    target = str(dataset["target_column"])
    features = _string_list(dataset["feature_columns"], field="feature_columns")
    validation_indices = _int_list(split["validation_indices"], field="validation_indices")
    identifier_columns = _string_list(dataset["identifier_columns"], field="identifier_columns")
    validation = train.iloc[validation_indices]
    fitting = train.drop(index=validation.index)
    numeric = [column for column in features if pd.api.types.is_numeric_dtype(fitting[column])]
    categorical = [column for column in features if column not in numeric]
    preprocess = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
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
    )
    model = Pipeline(
        [
            ("preprocess", preprocess),
            (
                "model",
                LogisticRegression(
                    C=config.c, max_iter=config.max_iter, random_state=context.random_seed or 42
                ),
            ),
        ]
    )
    model.fit(fitting[features], fitting[target])
    validation_prediction = model.predict(validation[features])
    probabilities = model.predict_proba(validation[features])[:, 1]
    validation_output = validation[[*identifier_columns, target]].copy()
    validation_output["prediction"] = validation_prediction
    validation_output["probability"] = probabilities
    validation_path = context.workdir / "validation-predictions.csv"
    validation_output.to_csv(validation_path, index=False)
    model.fit(train[features], train[target])
    test_output = test[[*identifier_columns]].copy()
    test_output["Survived" if target == "Survived" else "prediction"] = model.predict(
        test[features]
    )
    test_path = context.workdir / "test-predictions.csv"
    test_output.to_csv(test_path, index=False)
    metadata = _write_json(
        context.workdir / "naive-logistic-metadata.json",
        {
            "features": features,
            "numeric": numeric,
            "categorical": categorical,
            "estimator": "LogisticRegression",
            "c": config.c,
        },
    )
    return ComponentRunOutput(
        outputs={
            "validation_predictions": validation_path,
            "test_predictions": test_path,
            "model_metadata": metadata,
        }
    )


def evaluate_classification(context: ComponentExecutionContext) -> ComponentRunOutput:
    config: ClassificationEvaluatorConfig = context.config
    values = pd.read_csv(context.inputs["validation_predictions"])
    target = next(
        column
        for column in values.columns
        if column not in {"PassengerId", "prediction", "probability"}
    )
    metrics: dict[str, float | int | str | bool | None] = {
        "accuracy": float(accuracy_score(values[target], values["prediction"])),
        "macro_f1": float(f1_score(values[target], values["prediction"], average="macro")),
    }
    if len(set(values[target])) == 2:
        metrics["roc_auc"] = float(roc_auc_score(values[target], values["probability"]))
    evaluation = _write_json(
        context.workdir / "evaluation.json",
        {
            "primary_metric": config.primary_metric,
            "primary_value": metrics[config.primary_metric],
            "metrics": metrics,
            "sample_count": len(values),
        },
    )
    return ComponentRunOutput(outputs={"evaluation": evaluation}, metrics=metrics)


def register_tabular_components(registry: ComponentRegistry) -> ComponentRegistry:
    definitions: list[tuple[ComponentSpec, type[BaseModel], ComponentHandler]] = [
        (
            ComponentSpec(
                component_id="tabular_csv_dataset",
                name="Tabular CSV dataset",
                version="1.0",
                description="Validate and describe explicit train/test CSV sources.",
                outputs=[ComponentPort(name="dataset", artifact_type="tabular_dataset")],
                supported_modalities=["tabular"],
                supported_problem_types=["classification", "regression"],
                owner="lasi",
            ),
            CsvDatasetConfig,
            load_csv_dataset,
        ),
        (
            ComponentSpec(
                component_id="stratified_holdout",
                name="Stratified holdout",
                version="1.0",
                description="Create a deterministic stratified validation split.",
                inputs=[ComponentPort(name="dataset", artifact_type="tabular_dataset")],
                outputs=[ComponentPort(name="split", artifact_type="tabular_split")],
                supported_modalities=["tabular"],
                supported_problem_types=["classification"],
                owner="lasi",
            ),
            StratifiedHoldoutConfig,
            stratified_holdout,
        ),
        (
            ComponentSpec(
                component_id="titanic_title_family_features",
                name="Titanic title and family features",
                version="1.0",
                description="Derive a reviewed title/family Titanic feature set.",
                inputs=[ComponentPort(name="dataset", artifact_type="tabular_dataset")],
                outputs=[ComponentPort(name="dataset", artifact_type="tabular_dataset")],
                supported_modalities=["tabular"],
                supported_problem_types=["classification"],
                owner="lasi",
                known_limitations=["Applicable only to the Kaggle Titanic column contract."],
            ),
            TitanicTitleFamilyConfig,
            titanic_title_family_features,
        ),
        (
            ComponentSpec(
                component_id="naive_logistic_classifier",
                name="Naive logistic classifier",
                version="1.0",
                description=(
                    "A trusted logistic-regression baseline with conventional tabular "
                    "preprocessing."
                ),
                inputs=[
                    ComponentPort(name="dataset", artifact_type="tabular_dataset"),
                    ComponentPort(name="split", artifact_type="tabular_split"),
                ],
                outputs=[
                    ComponentPort(
                        name="validation_predictions", artifact_type="classification_predictions"
                    ),
                    ComponentPort(
                        name="test_predictions", artifact_type="classification_predictions"
                    ),
                    ComponentPort(name="model_metadata", artifact_type="model_metadata"),
                ],
                supported_modalities=["tabular"],
                supported_problem_types=["classification"],
                resource_requirements=BudgetEstimate(cpu_hours=0.1),
                owner="lasi",
                known_limitations=["Linear decision boundary; intended only as a baseline."],
            ),
            NaiveLogisticConfig,
            naive_logistic_classifier,
        ),
        (
            ComponentSpec(
                component_id="classification_evaluator",
                name="Classification evaluator",
                version="1.0",
                description=(
                    "Evaluate validation predictions with standard binary classification metrics."
                ),
                inputs=[
                    ComponentPort(
                        name="validation_predictions", artifact_type="classification_predictions"
                    )
                ],
                outputs=[ComponentPort(name="evaluation", artifact_type="evaluation")],
                supported_modalities=["tabular"],
                supported_problem_types=["classification"],
                owner="lasi",
            ),
            ClassificationEvaluatorConfig,
            evaluate_classification,
        ),
    ]
    for spec, model, handler in definitions:
        registry.register(spec, model, handler)
    return registry
