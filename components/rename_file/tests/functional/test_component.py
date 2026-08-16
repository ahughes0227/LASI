from pathlib import Path


def test_reference_component_source_exists() -> None:
    path = Path(__file__).parents[2] / "implementation/src/component.py"
    assert path.is_file()
