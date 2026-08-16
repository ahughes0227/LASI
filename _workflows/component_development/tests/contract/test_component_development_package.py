import json
from pathlib import Path


def test_component_development_workflow_package_is_present() -> None:
    path = Path(__file__).parents[2] / "workflow.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["workflow_id"] == "component_development"
    assert value["extension_policy"]["allow_execution"] is False
