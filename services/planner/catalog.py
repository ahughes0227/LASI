"""Governed graph projection for planner discovery.

The registries and installed packages remain authoritative. This catalog is a
rebuildable projection that makes relationships traversable and gives the
planner a deterministic post-retrieval contract check. It is intentionally not
the epistemic knowledge graph and does not authorize execution.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from services.capabilities import CapabilityRegistry
from services.components import ComponentRegistry
from services.memory import (
    OperationalMemory,
    PlannerCatalogEdgeRecord,
    PlannerCatalogNodeRecord,
)
from services.workflows import WorkflowRegistry

from .models import PlannerCandidate, PlannerCatalogEdge, PlannerCatalogNode, PlannerPath

if TYPE_CHECKING:
    from services.contracts import CapabilitySpec, ComponentSpec, WorkflowDefinition

_TOKENS = re.compile(r"[a-z0-9]+")


class PlannerCatalog:
    """In-memory view of the persisted planner graph with traversal queries."""

    def __init__(
        self, nodes: Iterable[PlannerCatalogNode], edges: Iterable[PlannerCatalogEdge]
    ) -> None:
        self.nodes = {node.node_id: node for node in nodes}
        self.edges = tuple(edges)
        self._outgoing: dict[str, list[PlannerCatalogEdge]] = defaultdict(list)
        self._incoming: dict[str, list[PlannerCatalogEdge]] = defaultdict(list)
        for edge in self.edges:
            self._outgoing[edge.source_node_id].append(edge)
            self._incoming[edge.target_node_id].append(edge)

    def node(self, node_id: str) -> PlannerCatalogNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"planner catalog node is not registered: {node_id}") from exc

    def find_for_need(
        self,
        need: str,
        *,
        limit: int = 12,
        node_types: set[str] | None = None,
    ) -> list[PlannerCandidate]:
        """Find candidate nodes lexically; callers validate contracts afterward."""
        terms = set(_TOKENS.findall(need.lower()))
        candidates: list[PlannerCandidate] = []
        for node in self.nodes.values():
            if node_types is not None and node.node_type not in node_types:
                continue
            haystack = " ".join(
                [node.external_id, node.node_type, *(_string_values(node.payload))]
            ).lower()
            matched = sorted(term for term in terms if term in haystack)
            if matched:
                candidates.append(
                    PlannerCandidate(
                        node=node,
                        score=round(len(matched) / max(len(terms), 1), 6),
                        matched_terms=matched,
                    )
                )
        candidates.sort(key=lambda item: (-item.score, item.node.node_id))
        return candidates[:limit]

    def find_components_for_need(self, need: str, *, limit: int = 12) -> list[PlannerCandidate]:
        """Discover only component nodes; retrieval is not compatibility proof."""
        return self.find_for_need(need, limit=limit, node_types={"component"})

    def traverse(
        self,
        start_node_id: str,
        *,
        direction: str = "outgoing",
        edge_types: set[str] | None = None,
        max_depth: int = 3,
    ) -> list[PlannerPath]:
        """Return bounded paths from a node without treating them as executable plans."""
        self.node(start_node_id)
        if direction not in {"outgoing", "incoming"}:
            raise ValueError("direction must be outgoing or incoming")
        adjacency = self._outgoing if direction == "outgoing" else self._incoming
        paths: list[PlannerPath] = []
        queue: deque[tuple[str, list[str], list[str]]] = deque(
            [(start_node_id, [start_node_id], [])]
        )
        while queue:
            current, node_ids, types = queue.popleft()
            if len(types) >= max_depth:
                continue
            for edge in adjacency.get(current, []):
                if edge_types and edge.edge_type not in edge_types:
                    continue
                next_id = edge.target_node_id if direction == "outgoing" else edge.source_node_id
                if next_id in node_ids:
                    continue
                next_path = PlannerPath(
                    node_ids=[*node_ids, next_id], edge_types=[*types, edge.edge_type]
                )
                paths.append(next_path)
                queue.append((next_id, next_path.node_ids, next_path.edge_types))
        return paths

    def capabilities_for_component(self, component_id: str) -> list[PlannerCatalogNode]:
        component_nodes = self._nodes_by_external("component", component_id)
        ids = {node.node_id for node in component_nodes}
        return self._targets(ids, {"implements_capability"})

    def components_for_capability(self, capability_id: str) -> list[PlannerCatalogNode]:
        capability_nodes = self._nodes_by_external("capability", capability_id)
        ids = {node.node_id for node in capability_nodes}
        return self._targets(ids, {"requires_component"})

    def workflows_for_capability(self, capability_id: str) -> list[PlannerCatalogNode]:
        capability_nodes = self._nodes_by_external("capability", capability_id)
        ids = {node.node_id for node in capability_nodes}
        return self._sources(ids, {"uses_capability"})

    def workflows_for_components(self, component_ids: Iterable[str]) -> list[PlannerCatalogNode]:
        capability_ids = {
            node.node_id
            for component_id in component_ids
            for node in self.capabilities_for_component(component_id)
        }
        return sorted(
            {
                workflow.node_id: workflow
                for capability_id in capability_ids
                for workflow in self._sources({capability_id}, {"uses_capability"})
            }.values(),
            key=lambda node: node.node_id,
        )

    def impact_for_component(self, component_id: str) -> dict[str, list[PlannerCatalogNode]]:
        """Return affected capabilities and workflows for extension review."""
        capabilities = self.capabilities_for_component(component_id)
        workflows = self.workflows_for_components([component_id])
        return {"capabilities": capabilities, "workflows": workflows}

    def _nodes_by_external(self, node_type: str, external_id: str) -> list[PlannerCatalogNode]:
        return [
            node
            for node in self.nodes.values()
            if node.node_type == node_type and node.external_id == external_id
        ]

    def _targets(self, source_ids: set[str], edge_types: set[str]) -> list[PlannerCatalogNode]:
        return sorted(
            {
                edge.target_node_id: self.nodes[edge.target_node_id]
                for source_id in source_ids
                for edge in self._outgoing.get(source_id, [])
                if edge.edge_type in edge_types
            }.values(),
            key=lambda node: node.node_id,
        )

    def _sources(self, target_ids: set[str], edge_types: set[str]) -> list[PlannerCatalogNode]:
        return sorted(
            {
                edge.source_node_id: self.nodes[edge.source_node_id]
                for target_id in target_ids
                for edge in self._incoming.get(target_id, [])
                if edge.edge_type in edge_types
            }.values(),
            key=lambda node: node.node_id,
        )


class PlannerCatalogBuilder:
    """Project approved registry metadata into the planner catalog."""

    def __init__(
        self,
        capabilities: CapabilityRegistry,
        workflows: WorkflowRegistry,
        components: ComponentRegistry,
    ) -> None:
        self.capabilities = capabilities
        self.workflows = workflows
        self.components = components

    def build(self) -> PlannerCatalog:
        nodes: dict[str, PlannerCatalogNode] = {}
        edges: list[PlannerCatalogEdge] = []

        for capability in self.capabilities.all(include_drafts=True):
            node = _capability_node(capability)
            nodes[node.node_id] = node
        for component in self.components.all():
            node = _component_node(component)
            nodes[node.node_id] = node
        for workflow in self.workflows.all():
            workflow_node = _workflow_node(workflow)
            nodes[workflow_node.node_id] = workflow_node
            for item in workflow.nodes:
                node = PlannerCatalogNode(
                    node_id=(
                        f"workflow-node:{workflow.workflow_id}@{workflow.version}/{item.node_id}"
                    ),
                    node_type="workflow_node",
                    external_id=item.node_id,
                    version=workflow.version,
                    lifecycle="approved",
                    payload={"workflow_id": workflow.workflow_id, **item.model_dump(mode="json")},
                )
                nodes[node.node_id] = node
                _edge(edges, workflow_node.node_id, node.node_id, "contains_node")
                capability_id = f"capability:{item.capability}"
                capability_target = _latest_node_id(nodes, capability_id)
                if capability_target:
                    _edge(edges, node.node_id, capability_target, "uses_capability")
                    _edge(edges, workflow_node.node_id, capability_target, "uses_capability")

        for node in list(nodes.values()):
            if node.node_type != "capability":
                continue
            for dependency in node.payload.get("capability_dependencies", []):
                target = _latest_node_id(nodes, f"capability:{dependency}")
                if target:
                    _edge(edges, node.node_id, target, "depends_on_capability")
            for dependency in node.payload.get("component_dependencies", []):
                target = _latest_node_id(nodes, f"component:{dependency}")
                if target:
                    _edge(edges, node.node_id, target, "requires_component")
                    _edge(edges, target, node.node_id, "implements_capability")
        return PlannerCatalog(nodes.values(), edges)

    def persist(self, memory: OperationalMemory) -> PlannerCatalog:
        """Replace only the derived planner projection in one transaction."""
        catalog = self.build()
        with memory.transaction() as session:
            session.execute(delete(PlannerCatalogEdgeRecord))
            session.execute(delete(PlannerCatalogNodeRecord))
            for node in catalog.nodes.values():
                session.add(
                    PlannerCatalogNodeRecord(
                        node_id=node.node_id,
                        node_type=node.node_type,
                        external_id=node.external_id,
                        version=node.version,
                        lifecycle=node.lifecycle,
                        payload=node.payload,
                    )
                )
            session.flush()
            for edge in catalog.edges:
                session.add(
                    PlannerCatalogEdgeRecord(
                        edge_id=edge.edge_id,
                        source_node_id=edge.source_node_id,
                        target_node_id=edge.target_node_id,
                        edge_type=edge.edge_type,
                        status=edge.status,
                    )
                )
        return catalog

    @staticmethod
    def load(memory: OperationalMemory) -> PlannerCatalog:
        with memory.read_session() as session:
            nodes = [
                PlannerCatalogNode(
                    node_id=row.node_id,
                    node_type=row.node_type,
                    external_id=row.external_id,
                    version=row.version,
                    lifecycle=row.lifecycle,
                    payload=row.payload,
                )
                for row in session.scalars(select(PlannerCatalogNodeRecord))
            ]
            edges = [
                PlannerCatalogEdge(
                    edge_id=row.edge_id,
                    source_node_id=row.source_node_id,
                    target_node_id=row.target_node_id,
                    edge_type=row.edge_type,
                    status=row.status,
                )
                for row in session.scalars(select(PlannerCatalogEdgeRecord))
            ]
        return PlannerCatalog(nodes, edges)


def _capability_node(item: CapabilitySpec) -> PlannerCatalogNode:
    return PlannerCatalogNode(
        node_id=f"capability:{item.capability_id}@{item.version}",
        node_type="capability",
        external_id=item.capability_id,
        version=item.version,
        lifecycle=item.lifecycle,
        payload=item.model_dump(mode="json"),
    )


def _component_node(item: ComponentSpec) -> PlannerCatalogNode:
    return PlannerCatalogNode(
        node_id=f"component:{item.component_id}@{item.version}",
        node_type="component",
        external_id=item.component_id,
        version=item.version,
        lifecycle=item.lifecycle,
        payload=item.model_dump(mode="json"),
    )


def _workflow_node(item: WorkflowDefinition) -> PlannerCatalogNode:
    return PlannerCatalogNode(
        node_id=f"workflow:{item.workflow_id}@{item.version}",
        node_type="workflow",
        external_id=item.workflow_id,
        version=item.version,
        lifecycle="approved",
        payload=item.model_dump(mode="json"),
    )


def _latest_node_id(nodes: dict[str, PlannerCatalogNode], prefix: str) -> str | None:
    matches = [node for node_id, node in nodes.items() if node_id.startswith(prefix + "@")]
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: tuple(int(part) for part in (item.version or "0.0.0").split(".")),
    ).node_id


def _edge(edges: list[PlannerCatalogEdge], source: str, target: str, edge_type: str) -> None:
    edge_id = f"{source}->{edge_type}->{target}"
    if not any(edge.edge_id == edge_id for edge in edges):
        edges.append(
            PlannerCatalogEdge(
                edge_id=edge_id,
                source_node_id=source,
                target_node_id=target,
                edge_type=edge_type,
            )
        )


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _string_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _string_values(child)]
    return []
