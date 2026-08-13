"""Deterministic control policy for persistent, increasingly divergent research."""

from __future__ import annotations

from services.contracts import ResearchAttempt, ResearchLoopPolicy, ResearchLoopState

_COMPLETED_STATUSES = frozenset({"succeeded", "partial_success"})
_TRUE_BLOCKERS = frozenset(
    {
        "approval_required",
        "benchmark_isolation",
        "budget_exhausted",
        "dataset_unavailable",
        "policy_conflict",
        "privacy",
        "project_scope",
        "remote_trust",
    }
)


class ResearchLoopController:
    """Advance loop state without turning scientific recommendations into authority.

    Each plan still receives a deterministic DecisionRecord. Routine allowed plans
    continue without a conversational approval. Failed tools and insufficiently
    novel candidates are evidence, not terminal conditions.
    """

    def start(self, project_id: str, policy: ResearchLoopPolicy) -> ResearchLoopState:
        return ResearchLoopState(
            project_id=project_id,
            policy=policy,
            required_novelty=policy.initial_novelty_floor,
        )

    def record_attempt(
        self, state: ResearchLoopState, attempt: ResearchAttempt
    ) -> ResearchLoopState:
        if state.status != "running":
            raise ValueError("cannot append an attempt to a terminal research loop")
        if attempt.iteration != len(state.attempts) + 1:
            raise ValueError("attempt iteration must be contiguous")

        attempts = [*state.attempts, attempt]
        blocker = self._true_blocker(attempt)
        if blocker is not None:
            return state.model_copy(
                update={
                    "attempts": attempts,
                    "status": "blocked",
                    "next_phase": None,
                    "reason": f"true_blocker:{blocker}",
                }
            )

        if len(attempts) >= state.policy.max_iterations:
            return state.model_copy(
                update={
                    "attempts": attempts,
                    "status": "stopped",
                    "next_phase": None,
                    "reason": "iteration_budget_exhausted",
                }
            )

        completed = attempt.status in _COMPLETED_STATUSES and attempt.score is not None
        measured_novelty = self._measured_novelty(attempt, state.attempts)
        effective_novelty = min(attempt.novelty_score, measured_novelty)
        novel = not state.attempts or effective_novelty >= state.required_novelty
        improved = completed and self._improved(state, attempt.score)

        best_score = state.best_score
        best_attempt_id = state.best_attempt_id
        failures = state.non_improving_novel_attempts
        required_novelty = state.required_novelty
        reason = "continue_research_loop"

        if improved:
            best_score = attempt.score
            best_attempt_id = attempt.attempt_id
            failures = 0
            required_novelty = state.policy.initial_novelty_floor
            reason = "objective_improved"
        elif completed and novel:
            failures += 1
            required_novelty = min(
                state.policy.maximum_novelty_floor,
                state.policy.initial_novelty_floor + state.policy.novelty_increment * failures,
            )
            reason = "novel_attempt_did_not_improve"
        elif completed:
            reason = "candidate_insufficiently_divergent"
        else:
            reason = "recoverable_attempt_failure"

        if failures >= state.policy.plateau_patience:
            return state.model_copy(
                update={
                    "attempts": attempts,
                    "best_score": best_score,
                    "best_attempt_id": best_attempt_id,
                    "non_improving_novel_attempts": failures,
                    "required_novelty": required_novelty,
                    "status": "plateaued",
                    "next_phase": None,
                    "reason": "plateau_after_divergent_attempts",
                }
            )

        return state.model_copy(
            update={
                "attempts": attempts,
                "best_score": best_score,
                "best_attempt_id": best_attempt_id,
                "non_improving_novel_attempts": failures,
                "required_novelty": required_novelty,
                "next_phase": "explore",
                "reason": reason,
            }
        )

    @staticmethod
    def _true_blocker(attempt: ResearchAttempt) -> str | None:
        if attempt.status != "blocked" or not attempt.failure_reason:
            return None
        return next(
            (name for name in _TRUE_BLOCKERS if name in attempt.failure_reason),
            None,
        )

    @staticmethod
    def _improved(state: ResearchLoopState, score: float) -> bool:
        if state.best_score is None:
            return True
        delta = score - state.best_score
        if state.policy.objective_direction == "minimize":
            delta = -delta
        return delta > state.policy.minimum_meaningful_improvement

    @staticmethod
    def _measured_novelty(attempt: ResearchAttempt, prior_attempts: list[ResearchAttempt]) -> float:
        """Return distance from the most similar prior approach signature."""
        if not prior_attempts:
            return 1.0
        candidate = {part.strip().lower() for part in attempt.approach_signature if part.strip()}
        if not candidate:
            return 0.0
        greatest_similarity = 0.0
        for prior in prior_attempts:
            previous = {part.strip().lower() for part in prior.approach_signature if part.strip()}
            union = candidate | previous
            similarity = len(candidate & previous) / len(union) if union else 1.0
            greatest_similarity = max(greatest_similarity, similarity)
        return 1.0 - greatest_similarity
