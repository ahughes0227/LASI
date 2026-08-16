"""Package hashes must bind file content, not build and editor caches."""

from pathlib import Path

from services.capabilities.validation import hash_package
from services.components.package_validation import hash_component_package
from services.core import is_package_content
from services.workflows.package_validation import hash_workflow_package

HASHERS = (hash_component_package, hash_package, hash_workflow_package)


def _package(root: Path) -> Path:
    package = root / "example_component"
    (package / "implementation" / "src").mkdir(parents=True)
    (package / "tests" / "contract").mkdir(parents=True)
    (package / "component.yaml").write_text("component_id: example\n", encoding="utf-8")
    source = package / "implementation" / "src" / "component.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (package / "tests" / "contract" / "test_contract.py").write_text("pass\n", encoding="utf-8")
    return package


def _add_caches(package: Path) -> None:
    """Reproduce exactly what running the package's own tests leaves behind."""
    for directory in (
        package / "implementation" / "src" / "__pycache__",
        package / "tests" / "contract" / "__pycache__",
        package / ".pytest_cache" / "v",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    (package / "implementation" / "src" / "__pycache__" / "component.cpython-314.pyc").write_bytes(
        b"\x00cached bytecode"
    )
    (package / "tests" / "contract" / "__pycache__" / "test_contract.cpython-314.pyc").write_bytes(
        b"\x00cached bytecode"
    )
    (package / ".pytest_cache" / "v" / "lastfailed").write_text("{}", encoding="utf-8")
    (package / ".DS_Store").write_bytes(b"\x00finder metadata")


def test_running_package_tests_does_not_change_its_hash(tmp_path: Path) -> None:
    package = _package(tmp_path)
    before = [hasher(package) for hasher in HASHERS]

    _add_caches(package)

    assert [hasher(package) for hasher in HASHERS] == before


def test_package_hash_still_tracks_real_content_changes(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _add_caches(package)
    before = [hasher(package) for hasher in HASHERS]

    source = package / "implementation" / "src" / "component.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")

    assert all(
        after != original
        for after, original in zip([hasher(package) for hasher in HASHERS], before, strict=True)
    )


def test_installed_component_package_hash_is_reproducible() -> None:
    """The repository's own component package must hash the same on every run."""
    package = Path(__file__).parents[1] / "components" / "rename_file"

    assert hash_component_package(package) == hash_component_package(package)


def test_package_content_predicate_excludes_generated_files() -> None:
    assert is_package_content(Path("implementation/src/component.py"))
    assert not is_package_content(Path("implementation/src/__pycache__/component.cpython-314.pyc"))
    assert not is_package_content(Path("implementation/src/component.pyc"))
    assert not is_package_content(Path(".pytest_cache/v/lastfailed"))
    assert not is_package_content(Path("tests/.DS_Store"))
