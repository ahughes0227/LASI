"""Preview, authorization, and safe application of derived-artifact mutations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, Protocol

from .models import DomainFact, DomainStateSnapshot, PredicateResult
from .mutation_models import MutationAuthorization, MutationPreview, MutationResult
from .predicates import PredicateEvaluator


class MutationHandler(Protocol):
    def preview(self, request: object) -> MutationPreview: ...

    def apply(self, preview: MutationPreview, workdir: Path) -> tuple[Path, list[DomainFact]]: ...

    def compensate(self, preview: MutationPreview, output: Path, workdir: Path) -> Path: ...


class MutationDecisionLookup(Protocol):
    def authorization_for(self, preview: MutationPreview) -> MutationAuthorization: ...


class GovernedMutationRunner:
    """Run one mutation under a stable source snapshot and an existing decision."""

    def __init__(self, evaluator: PredicateEvaluator | None = None):
        self._evaluator = evaluator or PredicateEvaluator()

    def run(
        self,
        preview: MutationPreview,
        handler: MutationHandler,
        decision_lookup: MutationDecisionLookup,
        snapshot: DomainStateSnapshot,
        workdir: Path,
    ) -> MutationResult:
        if workdir.exists():
            raise FileExistsError(f"mutation workdir already exists: {workdir}")
        workdir.mkdir(parents=True)

        source = Path(preview.source_ref)
        if not source.is_absolute() or not source.is_file():
            return self._result(preview, "blocked", "source_ref must be an existing absolute file")

        source_hash = self._hash(source)
        if source_hash != preview.source_hash:
            return self._result(preview, "blocked", "source hash does not match mutation preview")

        preconditions = list(self._evaluator.evaluate_all(preview.required_preconditions, snapshot))
        if any(not result.satisfied for result in preconditions):
            return self._result(
                preview,
                "blocked",
                "one or more mutation preconditions are not satisfied",
                validation_results=preconditions,
            )

        authorization = decision_lookup.authorization_for(preview)
        if not authorization.decision_id:
            return self._result(
                preview,
                "blocked",
                "mutation authorization requires a decision_id",
                validation_results=preconditions,
            )
        if authorization.mutation_id != preview.mutation_id:
            return self._result(
                preview,
                "blocked",
                "mutation authorization does not match preview",
                validation_results=preconditions,
            )
        if not authorization.allowed:
            return self._result(
                preview,
                "blocked",
                "mutation authorization is not allowed",
                validation_results=preconditions,
            )

        try:
            output, facts = handler.apply(preview, workdir)
            if self._hash(source) != source_hash:
                return self._result(
                    preview,
                    "failed",
                    "source file changed during mutation",
                    validation_results=preconditions,
                )
            output = self._confined_output(output, workdir)
            output_hash = self._hash(output)
            revised_snapshot = snapshot.with_facts(
                [*snapshot.facts, *facts], revision=snapshot.revision + 1
            )
            postconditions = list(
                self._evaluator.evaluate_all(preview.expected_postconditions, revised_snapshot)
            )
        except Exception as exc:  # record handler and mutation-boundary errors
            return self._result(
                preview,
                "failed",
                str(exc),
                validation_results=preconditions,
            )

        if all(result.satisfied for result in postconditions):
            return self._result(
                preview,
                "applied",
                output_ref=str(output),
                output_hash=output_hash,
                validation_results=postconditions,
            )

        error = "one or more mutation postconditions are not satisfied"
        if preview.compensation_action is None:
            return self._result(
                preview,
                "quarantined",
                error,
                output_ref=str(output),
                output_hash=output_hash,
                validation_results=postconditions,
            )

        try:
            compensation = handler.compensate(preview, output, workdir)
        except Exception as exc:
            return self._result(
                preview,
                "failed",
                f"{error}; compensation failed: {exc}",
                output_ref=str(output),
                output_hash=output_hash,
                validation_results=postconditions,
            )
        return self._result(
            preview,
            "compensated",
            error,
            output_ref=str(output),
            output_hash=output_hash,
            validation_results=postconditions,
            compensation_ref=str(compensation),
        )

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _confined_output(output: Path, workdir: Path) -> Path:
        resolved_workdir = workdir.resolve()
        resolved_output = output.resolve()
        try:
            resolved_output.relative_to(resolved_workdir)
        except ValueError as exc:
            raise ValueError("mutation output must be a file inside workdir") from exc
        if not resolved_output.is_file():
            raise ValueError("mutation output must be a file inside workdir")
        return resolved_output

    @staticmethod
    def _result(
        preview: MutationPreview,
        status: Literal["applied", "blocked", "failed", "compensated", "quarantined"],
        error: str | None = None,
        *,
        output_ref: str | None = None,
        output_hash: str | None = None,
        validation_results: list[PredicateResult] | None = None,
        compensation_ref: str | None = None,
    ) -> MutationResult:
        return MutationResult(
            mutation_id=preview.mutation_id,
            status=status,
            output_ref=output_ref,
            output_hash=output_hash,
            validation_results=validation_results or [],
            errors=[error] if error else [],
            compensation_ref=compensation_ref,
        )
