import json
from pathlib import Path


def test_rename_file_contract_is_generic() -> None:
    root = Path(__file__).parents[2]
    manifest = (root / "component.yaml").read_text(encoding="utf-8")
    schema = json.loads((root / "contract/config.schema.json").read_text(encoding="utf-8"))
    assert "rename_finance_pdfs" not in manifest
    assert "destination_name" in schema["properties"]
