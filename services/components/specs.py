"""Canonical serialization and validation for component experiment specifications."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from services.contracts import ExperimentSpec

from .registry import ComponentRegistry


@dataclass(frozen=True)
class ResolvedExperimentSpec:
    spec: ExperimentSpec
    resolved: dict[str, Any]
    content_hash: str

    def json_bytes(self) -> bytes:
        return json.dumps(self.resolved, indent=2, sort_keys=True).encode("utf-8")


class ExperimentSpecResolver:
    """Validate graph nodes against the registry and freeze explicit defaults."""

    def __init__(self, registry: ComponentRegistry) -> None:
        self.registry = registry

    def resolve(self, spec: ExperimentSpec) -> ResolvedExperimentSpec:
        node_ids: set[str] = set()
        outputs: dict[str, set[str]] = {}
        nodes: list[dict[str, Any]] = []
        for node in spec.component_graph:
            if node.node_id in node_ids:
                raise ValueError(f"duplicate component node_id: {node.node_id}")
            node_ids.add(node.node_id)
            registered = self.registry.get(node.component_id, node.component_version)
            if spec.execution_backend not in registered.spec.supported_execution_backends:
                raise ValueError(
                    f"component {node.component_id} does not support {spec.execution_backend}"
                )
            if (
                registered.spec.supported_modalities
                and spec.modality not in registered.spec.supported_modalities
            ):
                raise ValueError(
                    f"component {node.component_id} does not support modality {spec.modality}"
                )
            if (
                registered.spec.supported_problem_types
                and spec.problem_type not in registered.spec.supported_problem_types
            ):
                raise ValueError(
                    f"component {node.component_id} does not support "
                    f"problem type {spec.problem_type}"
                )
            config = self.registry.validate_config(
                node.component_id, node.config, node.component_version
            )
            required_inputs = {port.name for port in registered.spec.inputs if port.required}
            if required_inputs - set(node.inputs):
                missing_inputs = sorted(required_inputs - set(node.inputs))
                raise ValueError(f"component {node.node_id} is missing inputs: {missing_inputs}")
            allowed_inputs = {port.name for port in registered.spec.inputs}
            unknown_inputs = set(node.inputs) - allowed_inputs
            if unknown_inputs:
                raise ValueError(
                    f"component {node.node_id} has unknown inputs: {sorted(unknown_inputs)}"
                )
            for port_name, ref in node.inputs.items():
                # Absolute artifact references remain external even if their
                # filenames contain dots (as temporary paths commonly do).
                if Path(ref).is_absolute() or "." not in ref:
                    continue  # external artifact reference
                source_node, source_port = ref.split(".", 1)
                if source_node not in outputs or source_port not in outputs[source_node]:
                    raise ValueError(
                        f"component {node.node_id} references unavailable output {ref}"
                    )
                expected = next(
                    port.artifact_type for port in registered.spec.inputs if port.name == port_name
                )
                producer = self.registry.get(
                    next(
                        item.component_id
                        for item in spec.component_graph
                        if item.node_id == source_node
                    ),
                    next(
                        item.component_version
                        for item in spec.component_graph
                        if item.node_id == source_node
                    ),
                )
                actual = next(
                    port.artifact_type for port in producer.spec.outputs if port.name == source_port
                )
                if expected != actual:
                    raise ValueError(
                        f"incompatible edge {ref} -> {node.node_id}.{port_name}: "
                        f"{actual} != {expected}"
                    )
            outputs[node.node_id] = {port.name for port in registered.spec.outputs}
            nodes.append(
                {
                    "node_id": node.node_id,
                    "component_id": registered.spec.component_id,
                    "component_version": registered.spec.version,
                    "config": config.model_dump(mode="json", exclude_none=True),
                    "inputs": dict(sorted(node.inputs.items())),
                }
            )
        resolved = {
            "schema_version": spec.schema_version,
            "experiment_spec_id": spec.experiment_spec_id,
            "project_id": spec.project_id,
            "dataset_version_id": spec.dataset_version_id,
            "hypothesis": spec.hypothesis,
            "modality": spec.modality,
            "problem_type": spec.problem_type,
            "execution_backend": spec.execution_backend,
            "random_seed": spec.random_seed,
            "evaluation_policy": (
                spec.evaluation_policy.model_dump(mode="json", exclude_none=True)
                if spec.evaluation_policy
                else None
            ),
            "expected_outputs": list(spec.expected_outputs),
            "component_graph": nodes,
            "provenance": spec.provenance.model_dump(mode="json", exclude_none=True),
        }
        encoded = json.dumps(resolved, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return ResolvedExperimentSpec(
            spec=spec, resolved=resolved, content_hash=hashlib.sha256(encoded).hexdigest()
        )


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    """Load JSON or YAML as an input encoding; Pydantic remains authoritative."""
    source = Path(path)
    value = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("experiment specification must be a mapping")
    return ExperimentSpec.model_validate(value)
