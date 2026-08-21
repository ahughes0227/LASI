from __future__ import annotations

import asyncio

import pytest
from services.contracts import (
    ApprovalRecord,
    Belief,
    Evidence,
    Goal,
    IdentityGrant,
    IdentitySnapshot,
    MemoryContext,
    OperatorResult,
    OperatorSpec,
    Plan,
    PlanStep,
    RiskLevel,
    RunSummary,
)
from services.execution import DeterministicExecutor, ExecutionDenied
from services.ledger import SqliteLedger
from services.memory import InMemoryProjection, MemoryService
from services.operators import OperatorRegistry
from services.policy import ExplorationPolicy, PlanVerifier


def build_registry(counter: list[str]) -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register(
        OperatorSpec(name="analyze", description="Deterministic analysis.", version="1"),
        lambda invocation: (
            counter.append(invocation.step.step_id)
            or OperatorResult(status="succeeded", outputs={"value": 1})
        ),
    )
    return registry


def identity(*operators: str) -> IdentitySnapshot:
    return IdentitySnapshot(
        actor_id="planner",
        policy_version="test-v1",
        grants=(
            IdentityGrant(
                subject_id="planner",
                operators=frozenset(operators),
                max_risk=RiskLevel.LOW,
            ),
        ),
    )


def plan() -> Plan:
    return Plan(
        plan_id="plan-1",
        goal=Goal(goal_id="goal-1", project_id="project-1", objective="learn"),
        proposed_by="planner",
        steps=(
            PlanStep(
                step_id="step-1", operator="analyze", rationale="establish evidence"
            ),
        ),
    )


def test_verifier_and_executor_replay_idempotently() -> None:
    calls: list[str] = []
    registry = build_registry(calls)
    ledger = SqliteLedger()
    proposal = plan()
    verification = PlanVerifier(registry).verify(
        proposal,
        identity=identity("analyze"),
        memory=MemoryContext(project_id="project-1"),
    )
    ledger.record_plan(proposal)
    ledger.record_decision(verification)
    executor = DeterministicExecutor(registry, ledger)
    assert executor.execute(proposal, verification).status == "succeeded"
    assert executor.execute(proposal, verification).steps[0].reused is True
    assert calls == ["step-1"]


def test_executor_rejects_plan_changed_after_verification() -> None:
    registry = build_registry([])
    ledger = SqliteLedger()
    proposal = plan()
    verification = PlanVerifier(registry).verify(
        proposal,
        identity=identity("analyze"),
        memory=MemoryContext(project_id="project-1"),
    )
    ledger.record_plan(proposal)
    ledger.record_decision(verification)
    changed = proposal.model_copy(
        update={
            "steps": (
                proposal.steps[0].model_copy(update={"arguments": {"surprise": True}}),
            )
        }
    )
    with pytest.raises(ExecutionDenied):
        DeterministicExecutor(registry, ledger).execute(changed, verification)


def test_executor_rejects_unrecorded_but_well_formed_decision() -> None:
    registry = build_registry([])
    proposal = plan()
    verification = PlanVerifier(registry).verify(
        proposal,
        identity=identity("analyze"),
        memory=MemoryContext(project_id="project-1"),
    )
    with pytest.raises(ExecutionDenied):
        DeterministicExecutor(registry, SqliteLedger()).execute(proposal, verification)


def test_identity_graph_denies_ungranted_operator() -> None:
    registry = build_registry([])
    result = PlanVerifier(registry).verify(
        plan(),
        identity=identity("different"),
        memory=MemoryContext(project_id="project-1"),
    )
    assert result.allowed is False
    assert result.findings[0].code == "identity_denied"


def test_high_risk_approval_is_bound_to_plan_digest_and_step() -> None:
    registry = OperatorRegistry()
    registry.register(
        OperatorSpec(
            name="mutate",
            description="Change authoritative state.",
            version="1",
            risk=RiskLevel.HIGH,
        ),
        lambda _: OperatorResult(status="succeeded"),
    )
    proposal = Plan(
        plan_id="plan-risk",
        goal=Goal(goal_id="goal-risk", project_id="project-1", objective="change"),
        proposed_by="planner",
        steps=(
            PlanStep(
                step_id="mutate-1",
                operator="mutate",
                rationale="authorized change",
                approval_ref="approval-1",
            ),
        ),
    )
    ledger = SqliteLedger()
    verifier = PlanVerifier(registry, approval_checker=ledger.has_approval)
    risk_identity = IdentitySnapshot(
        actor_id="planner",
        policy_version="test-v1",
        grants=(
            IdentityGrant(
                subject_id="planner",
                operators=frozenset({"mutate"}),
                max_risk=RiskLevel.HIGH,
            ),
        ),
    )
    denied = verifier.verify(
        proposal,
        identity=risk_identity,
        memory=MemoryContext(project_id="project-1"),
    )
    assert denied.requires_approval is True
    ledger.record_approval(
        ApprovalRecord(
            approval_id="approval-1",
            plan_digest=proposal.digest(),
            step_id="mutate-1",
            approver_id="human-1",
        )
    )
    allowed = verifier.verify(
        proposal,
        identity=risk_identity,
        memory=MemoryContext(project_id="project-1"),
    )
    assert allowed.allowed is True


def test_external_context_creates_pressure_but_not_authority() -> None:
    registry = build_registry([])
    memory = MemoryContext(
        project_id="project-1",
        beliefs=(
            Belief(
                belief_id="belief-1",
                project_id="project-1",
                statement="A fragile assumption",
                confidence=0.3,
            ),
        ),
        evidence=(
            Evidence(
                evidence_id="external-1",
                project_id="project-1",
                source="paper",
                content="Try a different representation",
            ),
        ),
    )
    directives = ExplorationPolicy().directives(memory, registry)
    assert {item.kind for item in directives} == {
        "challenge_belief",
        "test_external_claim",
    }


def test_stagnation_forces_search_neighborhood_change() -> None:
    registry = build_registry([])
    memory = MemoryContext(
        project_id="project-1",
        recent_runs=tuple(
            RunSummary(
                run_id=f"run-{number}",
                plan_id=f"plan-{number}",
                status="succeeded",
                operator_names=("analyze",),
                outcome="no_improvement",
            )
            for number in range(3)
        ),
    )
    directives = ExplorationPolicy(stagnation_runs=3).directives(memory, registry)
    assert directives[-1].kind == "try_analogy"


def test_memory_combines_semantic_projection_and_external_evidence() -> None:
    async def scenario() -> None:
        belief = Belief(
            belief_id="belief-1",
            project_id="project-1",
            statement="class imbalance limits recall",
            confidence=0.7,
        )
        memory = MemoryService(SqliteLedger(), InMemoryProjection((belief,)))
        memory.add_evidence(
            Evidence(
                evidence_id="evidence-1",
                project_id="project-1",
                source="operator",
                content="recall is low",
            )
        )
        context = await memory.context(project_id="project-1", query="class recall")
        assert context.beliefs == (belief,)
        assert context.evidence[0].evidence_id == "evidence-1"

    asyncio.run(scenario())
