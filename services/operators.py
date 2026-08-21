"""Closed operator registry and deterministic invocation boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from .contracts import OperatorInvocation, OperatorResult, OperatorSpec


class OperatorHandler(Protocol):
    def __call__(self, invocation: OperatorInvocation) -> OperatorResult: ...


@dataclass(frozen=True)
class RegisteredOperator:
    spec: OperatorSpec
    handler: OperatorHandler
    input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = None

    def invoke(self, invocation: OperatorInvocation) -> OperatorResult:
        arguments: dict[str, Any] = invocation.step.arguments
        if self.input_model is not None:
            validated = self.input_model.model_validate(arguments)
            validated_step = invocation.step.model_copy(
                update={"arguments": validated.model_dump()}
            )
            invocation = invocation.model_copy(
                update={"step": validated_step}
            )
        result = self.handler(invocation)
        if self.output_model is not None and result.status == "succeeded":
            output = self.output_model.model_validate(result.outputs)
            result = result.model_copy(update={"outputs": output.model_dump()})
        return result


class OperatorRegistry:
    def __init__(self) -> None:
        self._operators: dict[str, RegisteredOperator] = {}

    def register(
        self,
        spec: OperatorSpec,
        handler: OperatorHandler,
        *,
        input_model: type[BaseModel] | None = None,
        output_model: type[BaseModel] | None = None,
    ) -> None:
        if spec.name in self._operators:
            raise ValueError(f"operator already registered: {spec.name}")
        self._operators[spec.name] = RegisteredOperator(
            spec=spec, handler=handler, input_model=input_model, output_model=output_model
        )

    def get(self, name: str) -> RegisteredOperator:
        try:
            return self._operators[name]
        except KeyError as exc:
            raise KeyError(f"unknown operator: {name}") from exc

    def specs(self) -> tuple[OperatorSpec, ...]:
        return tuple(item.spec for item in self._operators.values())


def function_operator(
    spec: OperatorSpec,
    function: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[OperatorSpec, OperatorHandler]:
    def handler(invocation: OperatorInvocation) -> OperatorResult:
        return OperatorResult(status="succeeded", outputs=function(invocation.step.arguments))

    return spec, handler
