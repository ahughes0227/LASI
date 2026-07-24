"""JSON Schema generation and validation for LASI contracts."""

from typing import Any

from pydantic import TypeAdapter

from .models import StrictModel


def contract_json_schema[ContractT: StrictModel](contract: type[ContractT]) -> dict[str, Any]:
    """Return the draft-compatible JSON Schema emitted by Pydantic."""

    return contract.model_json_schema()


def validate_contract[ContractT: StrictModel](contract: type[ContractT], value: Any) -> ContractT:
    """Validate a Python object or JSON-compatible mapping against a contract."""

    return TypeAdapter(contract).validate_python(value)


def validate_contract_json[ContractT: StrictModel](
    contract: type[ContractT], value: str | bytes
) -> ContractT:
    """Validate JSON text without first weakening it to an untyped dictionary."""

    return TypeAdapter(contract).validate_json(value)
