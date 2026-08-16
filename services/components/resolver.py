"""Component deduplication over planner discovery and authoritative registry metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from services.contracts import ComponentCandidate, ComponentResolution, ComponentSpec, Provenance

from .registry import ComponentRegistry

if TYPE_CHECKING:
    from services.planner import PlannerCatalog


class ComponentResolver:
    """Resolve a component request after retrieval has found candidate components."""

    def __init__(self, catalog: PlannerCatalog, registry: ComponentRegistry) -> None:
        self.catalog = catalog
        self.registry = registry

    def resolve(self, requested: ComponentSpec) -> ComponentResolution:
        query = " ".join(
            [
                requested.component_id,
                requested.name,
                requested.description or "",
                requested.responsibility or "",
                *requested.configuration_boundary,
            ]
        )
        candidates: list[ComponentCandidate] = []
        for retrieved in self.catalog.find_components_for_need(query):
            try:
                registered = self.registry.describe(
                    retrieved.node.external_id, retrieved.node.version
                )
            except ValueError:
                continue
            candidate = self._compare(
                requested,
                retrieved.node.node_id,
                retrieved.score,
                retrieved.matched_terms,
                registered,
            )
            candidates.append(candidate)

        candidates.sort(
            key=lambda item: (
                -item.responsibility_compatibility,
                -item.configuration_compatibility,
                -item.input_coverage,
                -item.output_coverage,
                item.component_id,
            )
        )
        best = candidates[0] if candidates else None
        selected: list[str] = []
        action = "new"
        missing: list[str] = []
        affected_capabilities: list[str] = []
        affected_workflows: list[str] = []
        if best is not None:
            selected = [best.component_id]
            missing = best.missing_requirements
            impact = self.catalog.impact_for_component(best.component_id)
            affected_capabilities = [node.external_id for node in impact["capabilities"]]
            affected_workflows = [node.external_id for node in impact["workflows"]]
            if (
                best.responsibility_compatibility >= 0.75
                and best.configuration_compatibility >= 0.75
                and best.input_coverage >= 1
                and best.output_coverage >= 1
                and not best.conflicting_exclusions
                and not missing
            ):
                action = "reuse"
            elif best.responsibility_compatibility >= 0.6:
                action = "extend"
        if action == "new":
            selected = []
            affected_capabilities = []
            affected_workflows = []
        return ComponentResolution(
            resolution_id=f"component-resolution-{uuid4().hex}",
            requested_component_id=requested.component_id,
            action=action,
            candidates=candidates,
            selected_component_ids=selected,
            missing_requirements=missing,
            affected_capability_ids=affected_capabilities,
            affected_workflow_ids=affected_workflows,
            rationale=self._rationale(action, best),
            created_at=datetime.now(UTC),
            provenance=Provenance(source_records=[item.catalog_node_id for item in candidates]),
        )

    @staticmethod
    def _compare(
        requested: ComponentSpec,
        node_id: str,
        retrieval_score: float,
        matched_terms: list[str],
        candidate: ComponentSpec,
    ) -> ComponentCandidate:
        requested_terms = _terms(
            requested.responsibility or requested.description or requested.name
        )
        candidate_terms = _terms(
            candidate.responsibility or candidate.description or candidate.name
        )
        responsibility = _coverage(requested_terms, candidate_terms)
        requested_config = set(requested.configuration_boundary)
        candidate_config = set(candidate.configuration_boundary)
        config = 1.0 if not requested_config else _coverage(requested_config, candidate_config)
        input_types = {port.artifact_type for port in requested.inputs if port.required}
        output_types = {port.artifact_type for port in requested.outputs if port.required}
        candidate_inputs = {port.artifact_type for port in candidate.inputs}
        candidate_outputs = {port.artifact_type for port in candidate.outputs}
        input_coverage = _set_coverage(input_types, candidate_inputs)
        output_coverage = _set_coverage(output_types, candidate_outputs)
        conflicts = sorted(set(requested.does_not) & set(candidate.does_not))
        missing: list[str] = []
        if requested.runtime.language != candidate.runtime.language:
            missing.append("runtime language differs")
        if (
            requested.operational_requirements.requires_network
            and not candidate.operational_requirements.requires_network
        ):
            missing.append("network requirement is not declared")
        return ComponentCandidate(
            catalog_node_id=node_id,
            component_id=candidate.component_id,
            version=candidate.version,
            retrieval_score=retrieval_score,
            matched_terms=matched_terms,
            responsibility_compatibility=responsibility,
            configuration_compatibility=config,
            input_coverage=input_coverage,
            output_coverage=output_coverage,
            conflicting_exclusions=conflicts,
            missing_requirements=missing,
        )

    @staticmethod
    def _rationale(action: str, candidate: ComponentCandidate | None) -> str:
        if candidate is None:
            return "No registered component candidate satisfied the requested responsibility."
        return (
            f"Selected {action} after planner retrieval and authoritative contract comparison "
            f"against {candidate.component_id}@{candidate.version}."
        )


def _terms(value: str) -> set[str]:
    return {part for part in value.lower().replace("_", " ").split() if len(part) > 2}


def _coverage(required: set[str], available: set[str]) -> float:
    if not required:
        return 1.0
    return len(required & available) / len(required)


def _set_coverage(required: set[str], available: set[str]) -> float:
    if not required:
        return 1.0
    return 1.0 if required.issubset(available) else len(required & available) / len(required)
