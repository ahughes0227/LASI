from pathlib import Path

from pydantic import BaseModel
from services.capabilities import CapabilityRegistry
from services.components import (
    ComponentDevelopmentService,
    ComponentRegistry,
    ComponentResolver,
)
from services.contracts import ComponentPort, ComponentSpec
from services.planner import PlannerCatalogBuilder
from services.workflows import WorkflowRegistry

ROOT = Path(__file__).parents[1]


class EmptyConfig(BaseModel):
    pass


def _catalog(registry: ComponentRegistry):
    capabilities = CapabilityRegistry()
    workflows = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    return PlannerCatalogBuilder(capabilities, workflows, registry).build()


def _rename_spec() -> ComponentSpec:
    return ComponentSpec(
        component_id="rename_file",
        name="Rename File",
        description="Rename one file artifact",
        responsibility="rename one file artifact",
        version="1.0.0",
        inputs=[ComponentPort(name="source", artifact_type="file")],
        outputs=[ComponentPort(name="renamed_file", artifact_type="file")],
        configuration_boundary=["destination_name", "overwrite_policy"],
    )


def test_planner_catalog_filters_component_discovery() -> None:
    registry = ComponentRegistry()
    registry.register(_rename_spec(), EmptyConfig, lambda **_: None)
    catalog = _catalog(registry)

    matches = catalog.find_components_for_need("rename finance PDFs")

    assert matches[0].node.node_type == "component"
    assert matches[0].node.external_id == "rename_file"


def test_component_resolution_uses_registry_contracts_after_retrieval() -> None:
    registry = ComponentRegistry()
    registry.register(_rename_spec(), EmptyConfig, lambda **_: None)
    resolver = ComponentResolver(_catalog(registry), registry)
    requested = _rename_spec().model_copy(
        update={"component_id": "rename_finance_pdfs", "name": "Rename Finance PDFs"}
    )

    resolution = resolver.resolve(requested)

    assert resolution.action == "reuse"
    assert resolution.selected_component_ids == ["rename_file"]


def test_component_service_does_not_scaffold_reuse(tmp_path: Path) -> None:
    registry = ComponentRegistry()
    registry.register(_rename_spec(), EmptyConfig, lambda **_: None)
    service = ComponentDevelopmentService(registry, _catalog(registry))
    requested = _rename_spec().model_copy(
        update={"component_id": "rename_finance_pdfs", "name": "Rename Finance PDFs"}
    )

    plan = service.plan(requested)

    assert plan.resolution.action == "reuse"
    assert plan.files_to_create == []
