"""Prior experience reaching a later decision.

The thesis these tests exist for: an episode recorded on one problem should change what
is chosen on a similar problem later, and should do so visibly. The negative cases matter
as much as the positive one — evidence from a different kind of problem, or from a plan
that never ran, must not vote.
"""

from datetime import UTC, datetime, timedelta

import pytest
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import (
    Project,
    ReasoningRubricRecord,
    ResearchAssignmentRecord,
    RuntimeTaskRecord,
    TaskAttemptRecord,
    TaskGraphProposalRecord,
)
from services.planner import (
    DomainGoal,
    DomainPlan,
    EpisodeInformedRanker,
    EpisodeRetriever,
    LexicographicPlanRanker,
    PlanCandidate,
    PlannedCapabilityStep,
    PlanningEpisodeRecorder,
    ProblemContext,
    fingerprint,
)

NOW = datetime.now(UTC)
TABULAR = ProblemContext(problem_type="classification", modality="tabular", scaffold_revision="1.0")


@pytest.fixture
def memory() -> OperationalMemory:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    store = OperationalMemory(create_session_factory(engine))
    store.add(
        Project(
            project_id="project-1",
            project_name="P",
            problem_type="classification",
            modality="tabular",
        )
    )
    return store


def _goal(*predicates: str, goal_id: str = "goal-1") -> DomainGoal:
    return DomainGoal(
        goal_id=goal_id,
        project_id="project-1",
        description="reach a state",
        desired_state=[
            {"subject": "project", "predicate": name, "operator": "equals", "value": True}
            for name in predicates
        ],
    )


def _plan(plan_id: str, goal: DomainGoal, capability_ids: list[str]) -> DomainPlan:
    return DomainPlan(
        plan_id=plan_id,
        goal=goal,
        observed_revision=1,
        status="planned",
        steps=[
            PlannedCapabilityStep(
                step_id=f"step-{index}", capability_id=capability, side_effect_class="read"
            )
            for index, capability in enumerate(capability_ids)
        ],
    )


def _finish(memory: OperationalMemory, assignment_id: str, status: str) -> None:
    """Give an assignment a terminal state and one attempt, so it has a real outcome."""
    memory.add(
        ResearchAssignmentRecord(
            assignment_id=assignment_id, project_id="project-1", objective="o", status=status
        )
    )
    if memory.get(ReasoningRubricRecord, "none") is None:
        memory.add(
            ReasoningRubricRecord(
                rubric_key="none", rubric_id="none", version="1.0", capability="research"
            )
        )
    memory.add(
        TaskGraphProposalRecord(
            proposal_id=f"proposal-{assignment_id}",
            assignment_id=assignment_id,
            project_id="project-1",
            observed_revision=1,
            status="accepted",
        )
    )
    memory.add(
        RuntimeTaskRecord(
            task_id=f"task-{assignment_id}",
            assignment_id=assignment_id,
            project_id="project-1",
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
            project_id="project-1",
            status="succeeded" if status == "completed" else "failed",
            agent_role="coordinator",
            lease_owner="runtime-1",
            lease_expires_at=NOW + timedelta(minutes=15),
            context_snapshot_id="ctx",
            started_at=NOW,
        )
    )


def _seed(
    memory: OperationalMemory,
    *,
    plan_id: str,
    capability_ids: list[str],
    predicates: tuple[str, ...] = ("ready",),
    context: ProblemContext = TABULAR,
    assignment_status: str = "completed",
) -> None:
    goal = _goal(*predicates, goal_id=f"{plan_id}-goal")
    recorder = PlanningEpisodeRecorder(memory)
    recorder.record(_plan(plan_id, goal, capability_ids), problem=fingerprint(goal, context))
    _finish(memory, f"assignment-{plan_id}", assignment_status)
    recorder.attach_execution(plan_id, assignment_id=f"assignment-{plan_id}")


def _candidates() -> list[PlanCandidate]:
    """Two admissible plans the default ranker separates only by alphabetical tie-break."""
    return [
        PlanCandidate(
            candidate_id=f"candidate-{index}",
            steps=(
                PlannedCapabilityStep(
                    step_id="s", capability_id=capability, side_effect_class="read"
                ),
            ),
            decisions=(),
        )
        for index, capability in enumerate(["alpha", "beta"])
    ]


def test_fingerprint_matches_on_shape_not_wording() -> None:
    reworded = DomainGoal(
        goal_id="other",
        project_id="project-1",
        description="a completely different description",
        desired_state=[
            {"subject": "project", "predicate": "ready", "operator": "equals", "value": False}
        ],
    )

    # Same subject, predicate and operator; different value and prose.
    assert fingerprint(_goal("ready"), TABULAR).similarity(fingerprint(reworded, TABULAR)) == 1.0


def test_fingerprint_refuses_to_compare_across_modalities() -> None:
    vision = ProblemContext(problem_type="classification", modality="vision")

    assert fingerprint(_goal("ready"), TABULAR).similarity(fingerprint(_goal("ready"), vision)) == 0


def test_retrieval_finds_the_prior_episode(memory: OperationalMemory) -> None:
    _seed(memory, plan_id="prior", capability_ids=["beta"])

    found = EpisodeRetriever(memory).similar(fingerprint(_goal("ready"), TABULAR))

    assert [episode.plan_id for episode in found] == ["prior"]
    assert found[0].succeeded is True


def test_retrieval_ignores_a_differently_shaped_problem(memory: OperationalMemory) -> None:
    _seed(memory, plan_id="prior", capability_ids=["beta"], predicates=("deployed",))

    assert EpisodeRetriever(memory).similar(fingerprint(_goal("ready"), TABULAR)) == []


def test_retrieval_ignores_episodes_with_no_fingerprint(memory: OperationalMemory) -> None:
    goal = _goal("ready")
    PlanningEpisodeRecorder(memory).record(_plan("unfindable", goal, ["beta"]))

    assert EpisodeRetriever(memory).similar(fingerprint(goal, TABULAR)) == []


def test_prior_success_changes_which_plan_is_chosen(memory: OperationalMemory) -> None:
    """The thesis: experience on an earlier problem changes a later decision."""
    goal = _goal("ready")
    candidates = _candidates()

    cold = LexicographicPlanRanker().rank(candidates, goal=goal)
    assert [c.capability_ids[0] for c in cold] == ["alpha", "beta"]  # alphabetical tie-break

    _seed(memory, plan_id="prior", capability_ids=["beta"])
    informed = EpisodeInformedRanker(EpisodeRetriever(memory), context=TABULAR)
    warm = informed.rank(candidates, goal=goal)

    # `beta` is now preferred because it worked on a problem of this shape.
    assert [c.capability_ids[0] for c in warm] == ["beta", "alpha"]
    assert informed.precedent(candidates, goal=goal)["candidate-1"] > 0


def test_prior_failure_is_evidence_too(memory: OperationalMemory) -> None:
    goal = _goal("ready")
    _seed(memory, plan_id="prior", capability_ids=["alpha"], assignment_status="failed")
    informed = EpisodeInformedRanker(EpisodeRetriever(memory), context=TABULAR)

    scores = informed.precedent(_candidates(), goal=goal)

    assert scores["candidate-0"] < 0
    assert [c.capability_ids[0] for c in informed.rank(_candidates(), goal=goal)] == [
        "beta",
        "alpha",
    ]


def test_an_undispatched_plan_does_not_vote(memory: OperationalMemory) -> None:
    """A plan that never ran has no outcome; counting it would invent evidence."""
    goal = _goal("ready")
    PlanningEpisodeRecorder(memory).record(
        _plan("never-run", goal, ["beta"]), problem=fingerprint(goal, TABULAR)
    )
    informed = EpisodeInformedRanker(EpisodeRetriever(memory), context=TABULAR)

    assert set(informed.precedent(_candidates(), goal=goal).values()) == {0.0}


def test_with_no_episodes_it_reduces_to_the_default_ranker(memory: OperationalMemory) -> None:
    goal = _goal("ready")
    candidates = _candidates()

    informed = EpisodeInformedRanker(EpisodeRetriever(memory), context=TABULAR)

    assert informed.rank(candidates, goal=goal) == LexicographicPlanRanker().rank(
        candidates, goal=goal
    )


def test_the_planner_itself_selects_differently_once_it_has_experience(
    memory: OperationalMemory,
) -> None:
    """End to end: search proposes the same admissible set, experience picks differently."""
    from services.capabilities import CapabilityRegistry
    from services.contracts import CapabilitySpec
    from services.domain import (
        CapabilityDomainContract,
        CapabilityDomainRegistry,
        DomainPolicyEvaluator,
        DomainPolicyRegistry,
        DomainStateSnapshot,
    )
    from services.planner import DomainStatePlanner

    def contract(capability_id: str) -> CapabilityDomainContract:
        return CapabilityDomainContract(
            capability_id=capability_id,
            capability_version="1.0.0",
            effects=[
                {
                    "operation": "assert",
                    "subject": "project",
                    "predicate": "ready",
                    "value": True,
                    "status": "inferred",
                }
            ],
            side_effect_class="read",
            provenance_refs=["test"],
        )

    contracts = [contract("alpha"), contract("beta")]
    capabilities = CapabilityRegistry()
    for item in contracts:
        capabilities.add(
            CapabilitySpec(
                capability_id=item.capability_id,
                name=item.capability_id,
                version="1.0.0",
                purpose="test",
                operations=["run"],
                lifecycle="approved",
            )
        )
    domain = CapabilityDomainRegistry.from_items(capabilities, contracts)
    policies = DomainPolicyEvaluator(DomainPolicyRegistry.from_items([]))
    goal = _goal("ready")
    snapshot = DomainStateSnapshot(project_id="project-1", revision=1, facts=[], created_at=NOW)

    cold = DomainStatePlanner(domain, policies).plan(goal, snapshot)
    assert [step.capability_id for step in cold.steps] == ["alpha"]

    _seed(memory, plan_id="prior", capability_ids=["beta"])
    warm = DomainStatePlanner(
        domain,
        policies,
        EpisodeInformedRanker(EpisodeRetriever(memory), context=TABULAR),
    ).plan(goal, snapshot)

    assert [step.capability_id for step in warm.steps] == ["beta"]
    assert warm.ranker_id == "episode-informed"
    # Same admissible set either way; only the preference moved.
    assert {tuple(a.capability_ids) for a in cold.considered_alternatives} == {("beta",)}
    assert {tuple(a.capability_ids) for a in warm.considered_alternatives} == {("alpha",)}
