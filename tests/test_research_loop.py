"""Tests for persistent research-loop routing and evidence-based stopping."""

from services.contracts import ResearchAttempt, ResearchLoopPolicy
from services.workflows import ResearchLoopController


def _attempt(
    iteration: int,
    *,
    score: float | None,
    novelty: float,
    status: str = "succeeded",
    failure_reason: str | None = None,
) -> ResearchAttempt:
    return ResearchAttempt(
        attempt_id=f"attempt-{iteration}",
        iteration=iteration,
        experiment_plan_id=f"plan-{iteration}",
        status=status,
        score=score,
        hypothesis=f"hypothesis-{iteration}",
        research_basis=[f"evidence-{iteration}"],
        approach_signature=[f"family-{iteration}"],
        novel_dimensions=["model_family"],
        novelty_score=novelty,
        failure_reason=failure_reason,
    )


def _policy(**changes: object) -> ResearchLoopPolicy:
    values: dict[str, object] = {
        "objective_metric": "score",
        "objective_direction": "maximize",
        "minimum_meaningful_improvement": 0.001,
        "plateau_patience": 4,
    }
    values.update(changes)
    return ResearchLoopPolicy(**values)


def test_improvement_resets_patience_and_novelty_pressure() -> None:
    controller = ResearchLoopController()
    state = controller.start("project-1", _policy())
    state = controller.record_attempt(state, _attempt(1, score=0.7, novelty=0.1))
    state = controller.record_attempt(state, _attempt(2, score=0.69, novelty=0.4))
    assert state.non_improving_novel_attempts == 1
    assert state.required_novelty == 0.4

    state = controller.record_attempt(state, _attempt(3, score=0.72, novelty=0.5))
    assert state.status == "running"
    assert state.best_score == 0.72
    assert state.non_improving_novel_attempts == 0
    assert state.required_novelty == 0.25


def test_only_completed_sufficiently_novel_attempts_count_toward_plateau() -> None:
    controller = ResearchLoopController()
    state = controller.start("project-1", _policy())
    state = controller.record_attempt(state, _attempt(1, score=0.7, novelty=0.1))
    state = controller.record_attempt(state, _attempt(2, score=0.69, novelty=0.3))
    state = controller.record_attempt(state, _attempt(3, score=0.68, novelty=0.2))
    state = controller.record_attempt(
        state, _attempt(4, score=None, novelty=0.9, status="failed", failure_reason="tool_error")
    )
    assert state.non_improving_novel_attempts == 1
    assert state.status == "running"

    for iteration, novelty in [(5, 0.5), (6, 0.65), (7, 0.8)]:
        state = controller.record_attempt(state, _attempt(iteration, score=0.68, novelty=novelty))

    assert state.status == "plateaued"
    assert state.reason == "plateau_after_divergent_attempts"
    assert state.non_improving_novel_attempts == 4


def test_recoverable_failure_continues_but_true_blocker_stops() -> None:
    controller = ResearchLoopController()
    state = controller.start("project-1", _policy())
    state = controller.record_attempt(
        state, _attempt(1, score=None, novelty=0.4, status="failed", failure_reason="tool_error")
    )
    assert state.status == "running"
    assert state.reason == "recoverable_attempt_failure"

    state = controller.record_attempt(
        state,
        _attempt(
            2,
            score=None,
            novelty=0.8,
            status="blocked",
            failure_reason="privacy policy prevents required transfer",
        ),
    )
    assert state.status == "blocked"
    assert state.reason == "true_blocker:privacy"


def test_minimization_uses_lower_score_as_improvement() -> None:
    controller = ResearchLoopController()
    state = controller.start("project-1", _policy(objective_direction="minimize"))
    state = controller.record_attempt(state, _attempt(1, score=0.5, novelty=0.2))
    state = controller.record_attempt(state, _attempt(2, score=0.4, novelty=0.4))
    assert state.best_score == 0.4
    assert state.best_attempt_id == "attempt-2"


def test_identical_signature_cannot_claim_high_novelty() -> None:
    controller = ResearchLoopController()
    state = controller.start("project-1", _policy())
    first = _attempt(1, score=0.7, novelty=1.0)
    state = controller.record_attempt(state, first)
    duplicate = _attempt(2, score=0.69, novelty=1.0).model_copy(
        update={"approach_signature": first.approach_signature}
    )

    state = controller.record_attempt(state, duplicate)

    assert state.status == "running"
    assert state.reason == "candidate_insufficiently_divergent"
    assert state.non_improving_novel_attempts == 0
