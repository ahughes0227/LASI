"""Immutable operator manifests and a closed registry."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from .contracts import OperatorSpec


@dataclass(frozen=True)
class RegisteredOperator:
    spec: OperatorSpec
    input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = None

    def validate_input(self, value: dict[str, object]) -> dict[str, object]:
        if self.input_model is None:
            return value
        return self.input_model.model_validate(value).model_dump(mode="json")

    def validate_output(self, value: dict[str, object]) -> dict[str, object]:
        if self.output_model is None:
            return value
        return self.output_model.model_validate(value).model_dump(mode="json")


class OperatorRegistry:
    def __init__(self) -> None:
        self._operators: dict[str, RegisteredOperator] = {}

    def register(
        self,
        spec: OperatorSpec,
        *,
        input_model: type[BaseModel] | None = None,
        output_model: type[BaseModel] | None = None,
    ) -> None:
        if spec.name in self._operators:
            raise ValueError(f"operator already registered: {spec.name}")
        if spec.input_schema and input_model is None:
            raise ValueError("input_schema requires an executable Pydantic input model")
        if spec.output_schema and output_model is None:
            raise ValueError("output_schema requires an executable Pydantic output model")
        input_schema = input_model.model_json_schema() if input_model else {}
        output_schema = output_model.model_json_schema() if output_model else {}
        if spec.input_schema and spec.input_schema != input_schema:
            raise ValueError("declared input_schema does not match its Pydantic model")
        if spec.output_schema and spec.output_schema != output_schema:
            raise ValueError("declared output_schema does not match its Pydantic model")
        resolved = spec.model_copy(
            update={"input_schema": input_schema, "output_schema": output_schema}
        )
        self._operators[spec.name] = RegisteredOperator(resolved, input_model, output_model)

    def get(self, name: str) -> RegisteredOperator:
        try:
            return self._operators[name]
        except KeyError as exc:
            raise KeyError(f"unknown operator: {name}") from exc

    def specs(self) -> tuple[OperatorSpec, ...]:
        return tuple(item.spec for item in self._operators.values())
