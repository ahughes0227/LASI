"""Translate policy-compliant domain plans into governed workflow definitions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from services.contracts import (
    WorkflowArtifactContract,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowPromptRef,
    WorkflowRubricRef,
)

if TYPE_CHECKING:
    from services.planner.domain_models import DomainPlan


class DomainWorkflowBridge:
    """Compile a planned domain capability sequence into a workflow proposal."""

    def __init__(self, binding_path: Path) -> None:
        self.binding_path = Path(binding_path).resolve()
        self.bindings = self._load_bindings()
        self._validate_bindings()

    def build_definition(
        self,
        plan: DomainPlan,
        *,
        workflow_id: str,
        version: str = "1.0",
    ) -> WorkflowDefinition:
        if plan.status not in {"planned", "satisfied"}:
            raise ValueError(f"domain plan status must be planned or satisfied: {plan.status}")
        if plan.status == "satisfied":
            return WorkflowDefinition(
                workflow_id=workflow_id,
                version=version,
                goal=plan.goal.description,
                inputs=[],
                outputs=[],
                nodes=[],
                metadata=self._metadata(plan),
            )

        nodes: list[WorkflowNode] = []
        inputs: list[str] = []
        established_predicates: list[Any] = []
        established_artifacts: set[str] = set()
        for index, step in enumerate(plan.steps):
            binding = self.bindings.get(step.capability_id)
            if binding is None:
                raise ValueError(f"missing domain workflow binding: {step.capability_id}")
            writes = [
                WorkflowArtifactContract(
                    artifact_id=f"domain_effect_{index:02d}_{_slug(effect.predicate)}",
                    artifact_type="domain/fact",
                )
                for effect in step.expected_effects
            ]
            reads = [
                *(artifact for previous in nodes for artifact in previous.writes),
                *(
                    WorkflowArtifactContract(
                        artifact_id=_predicate_artifact_id(predicate),
                        artifact_type="domain/fact",
                    )
                    for predicate in step.required_predicates
                    if not _predicate_established(predicate, established_predicates)
                ),
            ]
            for predicate in step.required_predicates:
                if not _predicate_established(predicate, established_predicates):
                    artifact_id = _predicate_artifact_id(predicate)
                    if artifact_id not in inputs:
                        inputs.append(artifact_id)

            if binding["task_type"] == "component_execution":
                missing = {
                    artifact
                    for artifact in ("experiment_plan", "experiment_decision")
                    if not _binding_established(
                        artifact, established_artifacts, established_predicates
                    )
                }
                if missing:
                    raise ValueError(
                        "component_execution requires established artifacts: "
                        + ", ".join(sorted(missing))
                    )

            node_id = f"step_{index:02d}_{step.capability_id.replace('.', '_').replace('-', '_')}"
            node = WorkflowNode(
                node_id=node_id,
                task_type=binding["task_type"],
                dependencies=[nodes[-1].node_id] if nodes else [],
                reads=_unique_artifacts(reads),
                writes=writes,
                prompt=WorkflowPromptRef(**binding["prompt"]),
                rubric=WorkflowRubricRef(**binding["rubric"]),
                skill=binding["skill"],
                capability=step.capability_id,
                completion_mode="required",
                experiment_plan_binding=(
                    "experiment_plan" if binding["task_type"] == "component_execution" else None
                ),
                decision_binding=(
                    "experiment_decision" if binding["task_type"] == "component_execution" else None
                ),
                priority=index,
                max_attempts=3,
            )
            nodes.append(node)
            established_artifacts.update(artifact.artifact_id for artifact in writes)
            established_predicates.extend(step.expected_effects)

        outputs = [
            _predicate_artifact_id(plan.goal.desired_state[index])
            for index in range(len(plan.goal.desired_state))
            if index not in plan.initially_satisfied_predicate_indexes
        ]
        return WorkflowDefinition(
            workflow_id=workflow_id,
            version=version,
            goal=plan.goal.description,
            inputs=inputs,
            outputs=outputs,
            nodes=nodes,
            metadata=self._metadata(plan),
        )

    def _load_bindings(self) -> dict[str, dict[str, Any]]:
        value = yaml.safe_load(self.binding_path.read_text(encoding="utf-8"))
        capabilities = value.get("capabilities") if isinstance(value, dict) else None
        if not isinstance(capabilities, dict):
            raise ValueError("domain workflow bindings must define capabilities")
        return cast(dict[str, dict[str, Any]], capabilities)

    def _validate_bindings(self) -> None:
        system_root = self.binding_path.parent
        repository_root = system_root.parent
        skills_root = repository_root / ".opencode" / "skills"
        workflows_root = repository_root / "_workflows"
        for capability_id, binding in self.bindings.items():
            for field in (
                "task_type",
                "skill",
                "prompt",
                "rubric",
                "source_workflow",
                "source_node",
            ):
                if field not in binding:
                    raise ValueError(f"binding for {capability_id} is missing {field}")
            if not (skills_root / binding["skill"]).is_dir():
                raise ValueError(f"unknown bound skill: {binding['skill']}")
            for category in ("workflow_prompts", "reasoning_rubrics"):
                asset = binding["prompt"] if category == "workflow_prompts" else binding["rubric"]
                asset_id_key = "prompt_id" if category == "workflow_prompts" else "rubric_id"
                path = system_root / category / asset[asset_id_key] / f"{asset['version']}.json"
                if not path.is_file():
                    raise ValueError(f"missing bound {category} asset: {path}")
            workflow_path = workflows_root / binding["source_workflow"] / "workflow.json"
            if not workflow_path.is_file():
                raise ValueError(f"missing source workflow: {binding['source_workflow']}")
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            source_nodes = {node["node_id"] for node in workflow.get("nodes", [])}
            if binding["source_node"] not in source_nodes:
                raise ValueError(
                    f"missing source node: {binding['source_workflow']}->{binding['source_node']}"
                )

    @staticmethod
    def _metadata(plan: DomainPlan) -> dict[str, Any]:
        return {
            "domain_plan_id": plan.plan_id,
            "observed_revision": plan.observed_revision,
            "policy_decision_count": len(plan.policy_decisions),
            "unresolved_predicate_count": len(plan.unresolved_predicate_indexes),
        }


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "predicate"


def _predicate_artifact_id(predicate: Any) -> str:
    return f"domain_predicate_{_slug(predicate.subject)}_{_slug(predicate.predicate)}"


def _predicate_established(predicate: Any, effects: list[Any]) -> bool:
    operator = getattr(predicate.operator, "value", predicate.operator)
    return any(
        effect.operation == "assert"
        and effect.subject == predicate.subject
        and effect.predicate == predicate.predicate
        and (operator in {"exists", "not_exists"} or effect.value == predicate.value)
        for effect in effects
    )


def _binding_established(name: str, artifacts: set[str], effects: list[Any]) -> bool:
    return name in artifacts or any(
        effect.operation == "assert" and effect.predicate == name for effect in effects
    )


def _unique_artifacts(artifacts: list[WorkflowArtifactContract]) -> list[WorkflowArtifactContract]:
    result: list[WorkflowArtifactContract] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.artifact_id not in seen:
            result.append(artifact)
            seen.add(artifact.artifact_id)
    return result
