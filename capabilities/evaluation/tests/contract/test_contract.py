import json
from pathlib import Path


def test_contracts_are_closed_object_schemas() -> None:
    root = Path(__file__).parents[2]
    for name in ("input", "output"):
        schema = json.loads((root / "contract" / f"{name}.schema.json").read_text())
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
