"""Build the local planner vector index from registered repository metadata."""

from pathlib import Path

from services.capabilities import CapabilityRegistry
from services.components import ComponentRegistry
from services.planner.catalog import PlannerCatalogBuilder
from services.planner.vector_index import PlannerVectorIndex
from services.workflows import WorkflowRegistry


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    capabilities = CapabilityRegistry.discover(root / "capabilities")
    capabilities.add_system_context(root / "system/capabilities")
    components = ComponentRegistry.discover(root / "components")
    workflows = WorkflowRegistry(root / "_workflows", asset_root=root / "system")
    workflows.install_all()
    catalog = PlannerCatalogBuilder(capabilities, workflows, components).build()
    index = PlannerVectorIndex.build(catalog)
    output = root / ".lasi" / "planner_catalog_vectors"
    index.save(output)
    print(f"vectorized {len(index.nodes)} planner nodes")
    print(f"saved {output.with_suffix('.npz')}")
    print(f"saved {output.with_suffix('.json')}")


if __name__ == "__main__":
    main()
