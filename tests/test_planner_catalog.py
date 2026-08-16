"""Tests for planner graph projection and traversal."""

from pathlib import Path

from pydantic import BaseModel
from services.capabilities import CapabilityRegistry
from services.components import ComponentRegistry
from services.contracts import ComponentPort, ComponentSpec
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.planner import PlannerCatalogBuilder
from services.workflows import WorkflowRegistry

ROOT = Path(__file__).parents[1]


class EmptyConfig(BaseModel):
    pass


def test_catalog_connects_components_capabilities_and_workflows() -> None:
    discovered = CapabilityRegistry.discover(ROOT / "capabilities")
    capabilities = CapabilityRegistry()
    for capability in discovered.all(include_drafts=True):
        if capability.capability_id == "eda":
            capability = capability.model_copy(
                update={"component_dependencies": ["dataset_profile"], "lifecycle": "approved"}
            )
        capabilities.add(capability)
    workflows = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflows.install("dataset_diagnostic")
    components = ComponentRegistry()
    components.register(
        ComponentSpec(
            component_id="dataset_profile",
            name="Dataset profile",
            version="1.0.0",
            inputs=[ComponentPort(name="dataset", artifact_type="dataset")],
            outputs=[ComponentPort(name="profile", artifact_type="dataset/profile")],
        ),
        EmptyConfig,
        lambda **_: None,
    )
    catalog = PlannerCatalogBuilder(capabilities, workflows, components).build()
    assert catalog.components_for_capability("eda")[0].external_id == "dataset_profile"
    assert any(
        workflow.external_id == "dataset_diagnostic"
        for workflow in catalog.workflows_for_capability("eda")
    )
    paths = catalog.traverse(
        "component:dataset_profile@1.0.0", edge_types={"implements_capability", "uses_capability"}
    )
    assert any(path.node_ids[-1].startswith("capability:eda@") for path in paths)


def test_catalog_persists_and_supports_need_discovery(tmp_path: Path) -> None:
    capabilities = CapabilityRegistry.discover(ROOT / "capabilities")
    workflows = WorkflowRegistry(ROOT / "_workflows", asset_root=ROOT / "system")
    workflows.install("dataset_diagnostic")
    components = ComponentRegistry()
    components.register(
        ComponentSpec(
            component_id="embedding_generator",
            name="Embedding generator",
            version="1.0.0",
            description="Generate embeddings for point cloud samples.",
            supported_modalities=["point_cloud"],
            outputs=[ComponentPort(name="embedding", artifact_type="embedding")],
        ),
        EmptyConfig,
        lambda **_: None,
    )
    builder = PlannerCatalogBuilder(capabilities, workflows, components)
    engine = create_engine(f"sqlite:///{tmp_path / 'planner.db'}")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    builder.persist(memory)

    loaded = PlannerCatalogBuilder.load(memory)
    matches = loaded.find_for_need("generate embeddings for point cloud samples")
    assert matches[0].node.external_id == "embedding_generator"
    assert loaded.node("workflow:dataset_diagnostic@1.0").node_type == "workflow"
