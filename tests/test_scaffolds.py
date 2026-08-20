"""One standard bench: every workspace of a kind renders the same, and says which
revision it came from.

The uniformity is the point. Evidence is compared across projects, so a project shaped
differently is not comparable to the others, and a project that cannot say which
template revision produced it cannot be shown to be comparable at all.
"""

from pathlib import Path

import pytest
import yaml
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import Project
from services.scaffolds import ScaffoldError, ScaffoldRegistry, ScaffoldService

PROJECT_DATA = {
    "project_id": "demo",
    "project_name": "Demo",
    "objective": "Find what limits accuracy.",
    "owner": "andrew",
    "problem_type": "classification",
    "modality": "tabular",
}

#: The ICM layout fixed by _architecture/15_CONTEXT_SYSTEM.md.
ICM_DIRECTORIES = ("00_task", "10_context", "20_work", "30_evidence", "40_output", "artifacts")


@pytest.fixture
def service() -> ScaffoldService:
    return ScaffoldService()


@pytest.fixture
def memory() -> OperationalMemory:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = OperationalMemory(create_session_factory(engine))
    store.add(
        Project(
            project_id="demo",
            project_name="Demo",
            problem_type="classification",
            modality="tabular",
        )
    )
    return store


def test_every_template_declares_an_identity_and_revision(service: ScaffoldService) -> None:
    available = service.available()

    assert set(available) >= {
        "adr",
        "capability_package",
        "component_package",
        "experiment",
        "project",
        "workflow_package",
    }
    for name in available:
        assert service.describe(name).template == name


def test_project_renders_the_canonical_icm_layout(service: ScaffoldService, tmp_path: Path) -> None:
    rendered = service.render("project", tmp_path / "demo", data=PROJECT_DATA)
    root = rendered.directory

    for directory in ICM_DIRECTORIES:
        assert (root / directory).is_dir(), directory
    assert (root / "00_task/objective.md").read_text().strip().endswith(PROJECT_DATA["objective"])
    assert (root / "20_work/experiments").is_dir()


def test_two_projects_from_one_revision_are_structurally_identical(
    service: ScaffoldService, tmp_path: Path
) -> None:
    first = service.render("project", tmp_path / "a", data={**PROJECT_DATA, "project_id": "a"})
    second = service.render("project", tmp_path / "b", data={**PROJECT_DATA, "project_id": "b"})

    def tree(root: Path) -> set[str]:
        return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}

    assert tree(first.directory) == tree(second.directory)
    assert first.revision == second.revision


def test_rendered_tree_records_the_revision_it_came_from(
    service: ScaffoldService, tmp_path: Path
) -> None:
    rendered = service.render("project", tmp_path / "demo", data=PROJECT_DATA)
    recorded = yaml.safe_load((rendered.directory / ".scaffold.yml").read_text())

    assert recorded == {"template": "project", "revision": rendered.revision}
    assert service.is_current(rendered.directory)


def test_a_tree_on_an_older_revision_is_not_current(
    service: ScaffoldService, tmp_path: Path
) -> None:
    rendered = service.render("project", tmp_path / "demo", data=PROJECT_DATA)
    (rendered.directory / ".scaffold.yml").write_text(
        'template: project\nrevision: "0.9"\n', encoding="utf-8"
    )

    assert service.is_current(rendered.directory) is False


def test_a_tree_nobody_scaffolded_has_no_revision(service: ScaffoldService, tmp_path: Path) -> None:
    (tmp_path / "hand-made").mkdir()

    with pytest.raises(ScaffoldError):
        service.revision_of(tmp_path / "hand-made")


def test_rendering_over_existing_work_is_refused(service: ScaffoldService, tmp_path: Path) -> None:
    service.render("project", tmp_path / "demo", data=PROJECT_DATA)

    with pytest.raises(ScaffoldError):
        service.render("project", tmp_path / "demo", data=PROJECT_DATA)


def test_unknown_template_is_refused(service: ScaffoldService, tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError):
        service.render("no_such_template", tmp_path / "x", data={})


def test_experiment_renders_with_a_falsifiable_hypothesis(
    service: ScaffoldService, tmp_path: Path
) -> None:
    rendered = service.render(
        "experiment",
        tmp_path / "exp-1",
        data={"experiment_id": "exp-1", "hypothesis": "Label noise limits accuracy."},
    )

    assert "Label noise limits accuracy." in (rendered.directory / "hypothesis.md").read_text()
    # A refuting condition is part of the shell so it cannot be quietly omitted.
    assert "What would refute it" in (rendered.directory / "hypothesis.md").read_text()
    assert (rendered.directory / "critique.md").is_file()


def test_package_templates_render_the_shell_only(service: ScaffoldService, tmp_path: Path) -> None:
    rendered = service.render(
        "capability_package",
        tmp_path / "pkg",
        data={"package_title": "Tables", "package_summary": "Infer tables"},
    )
    root = rendered.directory

    assert (root / "implementation/custom").is_dir()
    assert (root / "tests/contract/README.md").is_file()
    # Data files belong to the build plan, never to the template.
    assert not (root / "capability.yaml").exists()


def test_registration_records_the_revision(
    service: ScaffoldService, memory: OperationalMemory, tmp_path: Path
) -> None:
    registry = ScaffoldRegistry(memory)
    rendered = service.render("project", tmp_path / "demo", data=PROJECT_DATA)

    record = registry.register(rendered, project_id="demo")

    assert (record.template, record.revision) == ("project", rendered.revision)
    assert registry.outdated("project", rendered.revision) == []


def test_outdated_trees_are_identifiable(
    service: ScaffoldService, memory: OperationalMemory, tmp_path: Path
) -> None:
    registry = ScaffoldRegistry(memory)
    rendered = service.render("project", tmp_path / "demo", data=PROJECT_DATA)
    registry.register(rendered, project_id="demo")

    # The set a governed template update would have to act on.
    outdated = registry.outdated("project", "99.0")

    assert [item.revision for item in outdated] == [rendered.revision]
