from pathlib import Path

import yaml


def test_component_development_manifest_exists() -> None:
    path = Path(__file__).parents[2] / "capability.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert value["capability_id"] == "component_development"
