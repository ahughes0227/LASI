"""Falsification-oriented behavioral evaluation for domain planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from services.capabilities import CapabilityRegistry
from services.contracts import CapabilitySpec, Provenance
from services.contracts.models import StrictModel
from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainFact,
    DomainPolicy,
    DomainPolicyEvaluator,
    DomainPolicyRegistry,
    DomainStateSnapshot,
)
from services.planner import DomainGoal, DomainPlan, DomainStatePlanner
from services.workflows import DomainWorkflowBridge, validate_workflow


class DomainRuntimeFixture(StrictModel):
    case_id: str
    description: str
    facts: list[DomainFact]
    goal: DomainGoal
    policies: list[DomainPolicy]
    capabilities: list[CapabilityDomainContract]
    expected_status: str
    expected_capability_ids: list[str]
    forbidden_capability_ids: list[str]
    expected_policy_outcomes: dict[str, str] = Field(default_factory=dict)
    expected_unresolved_predicate_indexes: list[int]


class DomainRuntimeCaseResult(StrictModel):
    case_id: str
    passed: bool
    failures: list[str]
    plan: DomainPlan


class DomainRuntimeEvaluator:
    """Evaluate fixture expectations without installing or executing workflows."""

    def __init__(self, repository_root: Path | None = None) -> None:
        self.repository_root = (repository_root or Path(__file__).resolve().parents[2]).resolve()

    def evaluate_file(self, path: Path) -> DomainRuntimeCaseResult:
        fixture = DomainRuntimeFixture.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
        capability_ids = {contract.capability_id for contract in fixture.capabilities}
        if not capability_ids <= {"eda", "evaluation", "research", "modeling"}:
            raise ValueError("level 4 fixtures may only use registered capability IDs")

        capability_registry = self._capability_registry()
        contracts = CapabilityDomainRegistry.from_items(capability_registry, fixture.capabilities)
        policies = DomainPolicyEvaluator(DomainPolicyRegistry.from_items(fixture.policies))
        snapshot = DomainStateSnapshot(
            project_id=fixture.goal.project_id,
            revision=1,
            facts=fixture.facts,
            created_at=fixture.facts[0].observed_at if fixture.facts else self._fixed_time(),
        )
        plan = DomainStatePlanner(contracts, policies).plan(fixture.goal, snapshot)
        failures: list[str] = []
        actual_ids = [step.capability_id for step in plan.steps]
        if plan.status != fixture.expected_status:
            failures.append(f"status: expected {fixture.expected_status!r}, got {plan.status!r}")
        if actual_ids != fixture.expected_capability_ids:
            failures.append(f"capabilities: expected {fixture.expected_capability_ids!r}, got {actual_ids!r}")
        forbidden = set(actual_ids) & set(fixture.forbidden_capability_ids)
        if forbidden:
            failures.append(f"forbidden capabilities present: {sorted(forbidden)!r}")
        outcomes = {decision.action: decision.outcome for decision in plan.policy_decisions}
        for action, expected in fixture.expected_policy_outcomes.items():
            if outcomes.get(action) != expected:
                failures.append(
                    f"policy {action}: expected {expected!r}, got {outcomes.get(action)!r}"
                )
        if plan.unresolved_predicate_indexes != fixture.expected_unresolved_predicate_indexes:
            failures.append(
                "unresolved predicates: expected "
                f"{fixture.expected_unresolved_predicate_indexes!r}, got "
                f"{plan.unresolved_predicate_indexes!r}"
            )

        if plan.status == "planned":
            try:
                workflow = DomainWorkflowBridge(
                    self.repository_root / "system/domain_workflow_bindings.yaml"
                ).build_definition(plan, workflow_id=f"level4-{fixture.case_id}")
                validate_workflow(
                    workflow,
                    skills={path.name for path in (self.repository_root / ".opencode/skills").iterdir()},
                    capabilities={"eda", "evaluation", "research", "modeling"},
                    prompts={
                        (path.parent.name, path.stem)
                        for path in (self.repository_root / "system/workflow_prompts").glob("*/*.json")
                    },
                    rubrics={
                        (path.parent.name, path.stem)
                        for path in (self.repository_root / "system/reasoning_rubrics").glob("*/*.json")
                    },
                    profiles={},
                )
            except Exception as exc:
                failures.append(f"workflow validation: {exc}")

        return DomainRuntimeCaseResult(
            case_id=fixture.case_id,
            passed=not failures,
            failures=failures,
            plan=plan,
        )

    @staticmethod
    def _fixed_time() -> Any:
        from datetime import UTC, datetime

        return datetime(2026, 1, 1, tzinfo=UTC)

    @staticmethod
    def _capability_registry() -> CapabilityRegistry:
        registry = CapabilityRegistry()
        for capability_id in ("eda", "evaluation", "research", "modeling"):
            registry.add(
                CapabilitySpec(
                    capability_id=capability_id,
                    name=capability_id.title(),
                    version="1.0.0",
                    purpose=f"Level 4 behavioral evaluation capability: {capability_id}",
                    operations=["evaluate_domain_state"],
                    execution_kind="opencode_skill",
                    lifecycle="approved",
                    provenance=Provenance(source_path="level4://in-memory"),
                )
            )
        return registry

