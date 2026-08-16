import json
from pathlib import Path


def test_workflow_package_json_is_present_and_object() -> None:
    path = Path(__file__).parents[2] / "workflow.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
