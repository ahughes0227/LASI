"""Composing selection policies and running them over the same decisions.

The sweep is what makes ranker choice an empirical question instead of an argument. Its
one job is to be a fair comparison, so most of what is tested here is the conditions
under which a comparison does *not* count.
"""

from datetime import UTC, datetime

import pytest
from services.memory import Base, OperationalMemory, create_engine, create_session_factory
from services.memory.models import Project
from services.planner import (
    DomainGoal,
    EpisodeRetriever,
    PlanCandidate,
    PlannedCapabilityStep,
)
from services.planner.fingerprint import ProblemContext
from services.sweeps import (
    RankerSweep,
    RankerVariant,
    SweepResult,
    UnknownRankerError,
    VariantOutcome,
    build_ranker,
)

NOW = datetime.now(UTC)
TABULAR = ProblemContext(problem_type="classification", modality="tabular")


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


def _goal() -> DomainGoal:
    return DomainGoal(
        goal_id="goal-1",
        project_id="project-1",
        description="reach ready",
        desired_state=[
            {"subject": "project", "predicate": "ready", "operator": "equals", "value": True}
        ],
    )


def _candidates(*capability_ids: str) -> list[PlanCandidate]:
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
        for index, capability in enumerate(capability_ids)
    ]


def test_a_variant_must_name_a_policy_that_exists() -> None:
    """Config naming an import path would be arbitrary code execution by YAML."""
    with pytest.raises(UnknownRankerError):
        build_ranker(RankerVariant(name="x", kind="services.evil:Ranker"))


def test_episode_informed_requires_a_retriever() -> None:
    with pytest.raises(UnknownRankerError, match="retriever"):
        build_ranker(RankerVariant(name="informed", kind="episode_informed"))


def test_the_default_variant_never_diverges_from_itself(memory: OperationalMemory) -> None:
    sweep = RankerSweep([(_goal(), _candidates("alpha", "beta"))])
    variant = RankerVariant(name="default", kind="lexicographic")

    result = sweep.run({"default": build_ranker(variant)}, [variant])

    assert result.variants[0].differed_from_default == 0
    assert result.variants[0].divergence_rate == 0.0


def test_an_informed_variant_with_no_episodes_matches_the_default(
    memory: OperationalMemory,
) -> None:
    """No divergence here means there was nothing to learn from, not that it is inert."""
    variant = RankerVariant(name="informed", kind="episode_informed")
    ranker = build_ranker(variant, retriever=EpisodeRetriever(memory), context=TABULAR)
    sweep = RankerSweep([(_goal(), _candidates("alpha", "beta"))])

    result = sweep.run({"informed": ranker}, [variant])

    assert result.variants[0].ranker_id == "episode-informed"
    assert result.variants[0].differed_from_default == 0


def test_forced_moves_are_counted_separately_from_real_choices() -> None:
    """A decision with one admissible plan says nothing about a selection policy."""
    sweep = RankerSweep(
        [
            (_goal(), _candidates("only")),
            (_goal(), _candidates("alpha", "beta")),
        ]
    )
    variant = RankerVariant(name="default", kind="lexicographic")

    result = sweep.run({"default": build_ranker(variant)}, [variant])

    assert result.variants[0].decisions == 2
    assert result.variants[0].real_choices == 1


def test_divergence_rate_is_zero_when_nothing_was_ever_chosen() -> None:
    """Dividing by zero real choices would report a rate from no decisions at all."""
    outcome = VariantOutcome(name="v", ranker_id="r", ranker_version="1", decisions=3)

    assert outcome.divergence_rate == 0.0


def test_variants_over_different_decision_sets_are_not_comparable() -> None:
    """Such a comparison measures the sets, not the policies."""
    mismatched = SweepResult(
        variants=[
            VariantOutcome(name="a", ranker_id="x", ranker_version="1", decisions=10),
            VariantOutcome(name="b", ranker_id="y", ranker_version="1", decisions=4),
        ]
    )

    assert mismatched.comparable is False


def test_hydra_composes_the_configured_variants() -> None:
    """The consumer Hydra was adopted for: a matrix of policies over the same decisions."""
    pytest.importorskip("hydra", reason="needs the optional 'sweeps' extra")
    from services.sweeps import load_variants

    variants = load_variants(["default", "informed"])

    assert [variant.kind for variant in variants] == ["lexicographic", "episode_informed"]
    # Composed into validated contracts, not raw config objects.
    assert all(isinstance(variant, RankerVariant) for variant in variants)
