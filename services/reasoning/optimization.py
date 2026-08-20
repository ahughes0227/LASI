"""DSPy-backed reasoning programs and their offline optimisation.

DSPy is confined to this module.  Everything else in `services.reasoning` speaks in terms
of `ReasoningProgram`, so replacing or removing DSPy is a change to one file rather than
to the system's vocabulary (ADR-005).

Optimisation is an explicit offline operation.  Nothing here runs during a research loop,
and nothing here promotes what it produces: `optimize` returns a challenger, and
`challengers.promote` is the only thing that can change its standing.
"""

from __future__ import annotations

from typing import Any

from services.contracts import DiagnosticPacket
from services.providers.normalization import KNOWN_ACTIONS

from .challengers import package_hash
from .models import ReasoningCapabilitySpec

#: Kept small on purpose.  The value of this layer today is the evaluation and challenger
#: discipline, not the optimisation: with tens of episodes, a larger search fits noise
#: more thoroughly rather than learning more.
DEFAULT_MAX_DEMOS = 4


class DspyUnavailableError(RuntimeError):
    """DSPy is an optional extra; install it with `--extra dspy`."""


def _require_dspy() -> Any:
    try:
        import dspy
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised by the extra's absence
        raise DspyUnavailableError(
            "DSPy is not installed; install the 'dspy' extra to optimise reasoning programs"
        ) from exc
    return dspy


def build_signature() -> Any:
    """The reasoning task, in DSPy's terms.

    Field names mirror what the `ScientistReview` contract requires, so a program cannot
    be optimised toward an output shape that normalisation would then reject.

    Written as a string signature rather than a `dspy.Signature` subclass: subclassing a
    lazily imported module defeats static typing for no behavioural gain.
    """
    dspy = _require_dspy()
    # The recommendation vocabulary is closed: `normalize_review` rejects anything
    # outside it.  Naming the options in the signature means optimisation targets the
    # contract that will actually be enforced, rather than producing fluent
    # recommendations the provider layer then throws away.
    actions = ", ".join(sorted(KNOWN_ACTIONS))
    return dspy.Signature(
        "evidence -> primary_diagnosis, recommended_next_action, supporting_evidence",
        instructions=(
            "Identify what limits performance, grounded only in the supplied evidence. "
            "Cite the evidence references you relied on, comma separated. "
            f"recommended_next_action must be exactly one of: {actions}."
        ),
    )


class DspyReasoningProgram:
    """A `ReasoningProgram` implemented as a DSPy module."""

    def __init__(
        self,
        program_id: str,
        program_version: str,
        *,
        module: Any | None = None,
    ) -> None:
        dspy = _require_dspy()
        self.program_id = program_id
        self.program_version = program_version
        self.module = module or dspy.Predict(build_signature())

    def respond(self, packet: DiagnosticPacket, *, experiment_ids: list[str]) -> dict[str, Any]:
        prediction = self.module(evidence=_evidence_text(packet))
        references = [
            item.strip()
            for item in str(getattr(prediction, "supporting_evidence", "")).split(",")
            if item.strip()
        ]
        return {
            "review_id": f"{self.program_id}-{self.program_version}-{packet.diagnostic_packet_id}",
            "primary_diagnosis": prediction.primary_diagnosis,
            "diagnosis_confidence": 0.5,
            "recommended_next_action": prediction.recommended_next_action,
            "expected_value": "unstated",
            "supporting_evidence": references,
            "evidence_references": references,
            "experiment_ids": experiment_ids,
        }

    def artifact(self) -> dict[str, Any]:
        """The compiled program, in a form that can be hashed and reviewed.

        `dump_state` is what DSPy persists when saving a compiled program, so hashing it
        binds approval to the demonstrations and instructions that were actually reviewed.
        """
        state = self.module.dump_state()
        return {
            "program_id": self.program_id,
            "program_version": self.program_version,
            "state": state,
        }


def _evidence_text(packet: DiagnosticPacket) -> str:
    """Flatten a packet into the single evidence string the signature takes."""
    return "\n".join(
        f"{key}: {value}"
        for key, value in sorted(packet.model_dump(mode="json").items())
        if value not in (None, [], {}, "")
    )


def optimize(
    baseline: DspyReasoningProgram,
    trainset: list[Any],
    metric: Any,
    *,
    challenger_version: str,
    capability_id: str,
    rubric_id: str,
    rubric_version: str,
    max_demos: int = DEFAULT_MAX_DEMOS,
) -> tuple[DspyReasoningProgram, ReasoningCapabilitySpec]:
    """Compile an optimised challenger from recorded examples.

    Returns the program and its spec with standing `challenger`.  The standing is not a
    formality: nothing downstream will run a challenger as champion, and no argument
    about how well it scored can change that without an approval.
    """
    _require_dspy()
    from dspy.teleprompt import BootstrapFewShot

    optimiser = BootstrapFewShot(metric=metric, max_bootstrapped_demos=max_demos)
    compiled = optimiser.compile(baseline.module, trainset=trainset)
    challenger = DspyReasoningProgram(baseline.program_id, challenger_version, module=compiled)
    spec = ReasoningCapabilitySpec(
        program_id=challenger.program_id,
        program_version=challenger_version,
        capability_id=capability_id,
        rubric_id=rubric_id,
        rubric_version=rubric_version,
        standing="challenger",
        package_hash=package_hash(challenger.artifact()),
    )
    return challenger, spec
