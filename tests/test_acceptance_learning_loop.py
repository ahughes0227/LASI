"""Acceptance: does prior experience change a later decision, for the better?

This is the thesis the system exists to demonstrate, and the only test whose failure
would mean the architecture does not work rather than that some component is broken.

It replaces a checklist of "each subsystem emitted output" with one question. All eleven
subsystems can be working and the answer can still be no.

Execution is simulated: a deterministic outcome per capability stands in for running real
components, because what is under test is the decision loop, not the components. The
decisions themselves are real -- the symbolic planner produces them, and the ranker
chooses among them.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from services.capabilities import CapabilityRegistry
from services.contracts import CapabilitySpec
from services.domain import (
    CapabilityDomainContract,
    CapabilityDomainRegistry,
    DomainPolicyEvaluator,
    DomainPolicyRegistry,
    DomainStateSnapshot,
)
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import (
    Project,
    ReasoningRubricRecord,
    ResearchAssignmentRecord,
    RuntimeTaskRecord,
    TaskAttemptRecord,
    TaskGraphProposalRecord,
)
from services.observability import MlflowTracer, trace_from_plan
from services.planner import (
    DomainGoal,
    DomainStatePlanner,
    EpisodeInformedRanker,
    EpisodeRetriever,
    PlanningEpisodeRecorder,
    ProblemContext,
    RankingContractError,
    fingerprint,
)
from services.scaffolds import ScaffoldService

NOW = datetime.now(UTC)
CONTEXT = ProblemContext(problem_type="classification", modality="tabular", scaffold_revision="1.0")

#: The simulated world: one capability works on problems of this shape, one does not.
#: The default ranker cannot tell them apart -- both are single-step, side-effect-free,
#: and approval-free -- so it falls through to its alphabetical tie-break and picks the
#: one that fails. That tie-break is precisely what experience should replace.
OUTCOMES = {"alpha_probe": "failed", "beta_probe": "completed"}


@pytest.fixture
def memory() -> OperationalMemory:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = OperationalMemory(create_session_factory(engine))
    for project_id in ("project-a", "project-b"):
        store.add(
            Project(
                project_id=project_id,
                project_name=project_id,
                problem_type="classification",
                modality="tabular",
            )
        )
    store.add(
        ReasoningRubricRecord(
            rubric_key="none", rubric_id="none", version="1.0", capability="research"
        )
    )
    return store


@pytest.fixture
def planner_parts():
    def contract(capability_id: str) -> CapabilityDomainContract:
        return CapabilityDomainContract(
            capability_id=capability_id,
            capability_version="1.0.0",
            effects=[
                {
                    "operation": "assert",
                    "subject": "project",
                    "predicate": "diagnosed",
                    "value": True,
                    "status": "inferred",
                }
            ],
            side_effect_class="read",
            provenance_refs=["acceptance"],
        )

    contracts = [contract("alpha_probe"), contract("beta_probe")]
    capabilities = CapabilityRegistry()
    for item in contracts:
        capabilities.add(
            CapabilitySpec(
                capability_id=item.capability_id,
                name=item.capability_id,
                version="1.0.0",
                purpose="probe what limits performance",
                operations=["run"],
                lifecycle="approved",
            )
        )
    return (
        CapabilityDomainRegistry.from_items(capabilities, contracts),
        DomainPolicyEvaluator(DomainPolicyRegistry.from_items([])),
    )


def _goal(project_id: str, goal_id: str) -> DomainGoal:
    """The same problem shape, posed on two different projects."""
    return DomainGoal(
        goal_id=goal_id,
        project_id=project_id,
        description="determine what limits accuracy",
        desired_state=[
            {"subject": "project", "predicate": "diagnosed", "operator": "equals", "value": True}
        ],
    )


def _snapshot(project_id: str) -> DomainStateSnapshot:
    return DomainStateSnapshot(project_id=project_id, revision=1, facts=[], created_at=NOW)


def _simulate_execution(memory: OperationalMemory, plan, assignment_id: str) -> str:
    """Run the chosen plan in the simulated world and record what happened."""
    capability = plan.steps[0].capability_id
    status = OUTCOMES[capability]
    project_id = plan.goal.project_id
    memory.add(
        ResearchAssignmentRecord(
            assignment_id=assignment_id, project_id=project_id, objective="o", status=status
        )
    )
    memory.add(
        TaskGraphProposalRecord(
            proposal_id=f"proposal-{assignment_id}",
            assignment_id=assignment_id,
            project_id=project_id,
            observed_revision=1,
            status="accepted",
        )
    )
    memory.add(
        RuntimeTaskRecord(
            task_id=f"task-{assignment_id}",
            assignment_id=assignment_id,
            project_id=project_id,
            proposal_id=f"proposal-{assignment_id}",
            task_type="orchestration",
            agent_role="coordinator",
            status="completed",
            sequence=1,
            rubric_key="none",
        )
    )
    memory.add(
        TaskAttemptRecord(
            attempt_id=f"attempt-{assignment_id}",
            task_id=f"task-{assignment_id}",
            assignment_id=assignment_id,
            project_id=project_id,
            status="succeeded" if status == "completed" else "failed",
            agent_role="coordinator",
            lease_owner="runtime-1",
            lease_expires_at=NOW + timedelta(minutes=15),
            context_snapshot_id="ctx",
            started_at=NOW,
        )
    )
    return status


def test_prior_experience_produces_a_better_later_decision(
    memory: OperationalMemory, planner_parts, tmp_path: Path
) -> None:
    """Run A, then run B twice: once able to remember A, once not."""
    domain, policies = planner_parts
    recorder = PlanningEpisodeRecorder(memory)
    retriever = EpisodeRetriever(memory)
    tracer = MlflowTracer(f"sqlite:///{tmp_path / 'mlflow.db'}", experiment="acceptance")

    # --- Problem A ------------------------------------------------------------------
    # Planned cold, so the default ranker's alphabetical tie-break decides. It picks the
    # capability that does not work, and the attempt fails. That failure is the evidence.
    goal_a = _goal("project-a", "goal-a")
    plan_a = DomainStatePlanner(domain, policies).plan(goal_a, _snapshot("project-a"))
    assert [step.capability_id for step in plan_a.steps] == ["alpha_probe"]

    recorder.record(plan_a, problem=fingerprint(goal_a, CONTEXT))
    status_a = _simulate_execution(memory, plan_a, "assignment-a")
    recorder.attach_execution(plan_a.plan_id, assignment_id="assignment-a")
    assert status_a == "failed"

    # A second episode, so the successful alternative is also on the record. Without it
    # the system would know only what to avoid, not what to try.
    goal_a2 = _goal("project-a", "goal-a2")
    plan_a2 = DomainStatePlanner(domain, policies, _FixedChoiceRanker("beta_probe")).plan(
        goal_a2, _snapshot("project-a")
    )
    recorder.record(plan_a2, problem=fingerprint(goal_a2, CONTEXT))
    assert _simulate_execution(memory, plan_a2, "assignment-a2") == "completed"
    recorder.attach_execution(plan_a2.plan_id, assignment_id="assignment-a2")

    # --- Problem B, cold ------------------------------------------------------------
    goal_b = _goal("project-b", "goal-b")
    cold = DomainStatePlanner(domain, policies).plan(goal_b, _snapshot("project-b"))

    # --- Problem B, able to remember ------------------------------------------------
    informed = EpisodeInformedRanker(retriever, context=CONTEXT)
    warm = DomainStatePlanner(domain, policies, informed).plan(goal_b, _snapshot("project-b"))

    # 1. The decision changed.
    assert [step.capability_id for step in cold.steps] == ["alpha_probe"]
    assert [step.capability_id for step in warm.steps] == ["beta_probe"]

    # 2. From the same admissible set: experience moved the preference, not the legality.
    def considered(plan) -> set[tuple[str, ...]]:
        return {tuple(step.capability_id for step in plan.steps)} | {
            tuple(alternative.capability_ids) for alternative in plan.considered_alternatives
        }

    assert considered(cold) == considered(warm) == {("alpha_probe",), ("beta_probe",)}

    # 3. Better on a declared metric: the realised outcome of running each choice.
    assert _simulate_execution(memory, cold, "assignment-b-cold") == "failed"
    assert _simulate_execution(memory, warm, "assignment-b-warm") == "completed"

    # 4. Attributable to a retrieved episode, not to chance.
    precedent = informed.precedent(
        [candidate for candidate in _candidates_from(cold, warm)],
        goal=goal_b,
    )
    assert any(score > 0 for score in precedent.values())

    retrieved = retriever.similar(fingerprint(goal_b, CONTEXT))
    assert {episode.plan_id for episode in retrieved} == {plan_a.plan_id, plan_a2.plan_id}

    # 5. And it is on the record: the trace names the policy and what it chose from.
    run_id = tracer.log_planning_decision(
        trace_from_plan(
            warm,
            problem_digest=fingerprint(goal_b, CONTEXT).digest,
            scaffold_revision="1.0",
            precedent=precedent,
        )
    )
    from mlflow.tracking import MlflowClient

    recorded = MlflowClient(tracking_uri=tracer.tracking_uri).get_run(run_id).data
    assert recorded.params["ranker_id"] == "episode-informed"
    assert recorded.params["chosen_capability_ids"] == "beta_probe"
    assert recorded.metrics["was_a_real_choice"] == 1.0


class _FixedChoiceRanker:
    """Forces a particular admissible plan, to seed the second episode."""

    ranker_id = "fixed-choice"
    ranker_version = "1.0"

    def __init__(self, capability_id: str) -> None:
        self.capability_id = capability_id

    def rank(self, candidates, *, goal):
        return tuple(sorted(candidates, key=lambda c: c.capability_ids != (self.capability_id,)))


def _candidates_from(*plans):
    """Reconstruct the candidate set the ranker saw, for inspecting its scoring."""
    from services.planner import PlanCandidate, PlannedCapabilityStep

    seen: dict[str, PlanCandidate] = {}
    for plan in plans:
        for index, sequence in enumerate(
            [tuple(step.capability_id for step in plan.steps)]
            + [tuple(a.capability_ids) for a in plan.considered_alternatives]
        ):
            key = ",".join(sequence)
            seen.setdefault(
                key,
                PlanCandidate(
                    candidate_id=f"candidate-{len(seen)}",
                    steps=tuple(
                        PlannedCapabilityStep(
                            step_id=f"s{index}", capability_id=item, side_effect_class="read"
                        )
                        for item in sequence
                    ),
                    decisions=(),
                ),
            )
    return list(seen.values())


def test_a_learned_ranker_can_never_widen_the_admissible_set(
    memory: OperationalMemory, planner_parts
) -> None:
    """ADR-002's invariant, enforced in code rather than trusted.

    This is what makes learning safe here: a badly trained ranker produces a suboptimal
    legal plan, never an illegal one. Governance does not depend on model quality.
    """
    domain, policies = planner_parts

    class _Smuggler:
        ranker_id = "smuggler"
        ranker_version = "1.0"

        def rank(self, candidates, *, goal):
            from services.planner import PlanCandidate

            forged = PlanCandidate(candidate_id="forged", steps=(), decisions=())
            return (forged, *candidates)

    planner = DomainStatePlanner(domain, policies, _Smuggler())

    with pytest.raises(RankingContractError):
        planner.plan(_goal("project-b", "goal-b"), _snapshot("project-b"))


def test_every_workspace_is_the_same_bench_and_says_which(tmp_path: Path) -> None:
    """ADR-008's invariant.

    Episode retrieval compares evidence across projects. If two projects are shaped
    differently, or cannot say which template produced them, that comparison is
    confounded before any learning starts.
    """
    service = ScaffoldService()
    data = {
        "project_name": "P",
        "objective": "o",
        "owner": "a",
        "problem_type": "classification",
        "modality": "tabular",
    }
    first = service.render("project", tmp_path / "a", data={**data, "project_id": "a"})
    second = service.render("project", tmp_path / "b", data={**data, "project_id": "b"})

    def tree(root: Path) -> set[str]:
        return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}

    assert tree(first.directory) == tree(second.directory)
    assert service.revision_of(first.directory).revision == first.revision
    assert service.is_current(second.directory)
