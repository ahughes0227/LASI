"""A reasoning program running through the ordinary provider path, and being scored.

An LM-backed reviewer must be interchangeable with the mock one: same interface, same
normalisation, same privacy filtering. If it needed its own path, every guarantee the
provider layer offers would have to be re-established for it.
"""

import pytest
from services.contracts import (
    DiagnosticPacket,
    ProviderProfile,
    ReasoningCriterion,
    ReasoningRubric,
)
from services.contracts.models import PrivacyMode
from services.reasoning import (
    EvaluationCase,
    ProgramEvaluator,
    ReasoningScientistProvider,
    score_review,
)


@pytest.fixture
def packet() -> DiagnosticPacket:
    return DiagnosticPacket(
        diagnostic_packet_id="packet-1",
        project_id="project-1",
        problem_type="classification",
        dataset_version_id="dv-1",
        current_project_state="accuracy plateaus at 0.70",
        experiment_history=["exp-1"],
        privacy_mode=PrivacyMode.SUMMARY_ONLY,
    )


@pytest.fixture
def profile() -> ProviderProfile:
    return ProviderProfile(
        provider_id="reasoning-1",
        provider_type="local_model",
        model_name="dummy-1",
        privacy_capabilities=[PrivacyMode.SUMMARY_ONLY],
    )


@pytest.fixture
def rubric() -> ReasoningRubric:
    return ReasoningRubric(
        rubric_id="scientific_review",
        version="1.0",
        capability="critique",
        purpose="A review must be grounded and actionable.",
        criteria=[
            ReasoningCriterion(
                criterion_id="grounded",
                instruction="Cite the evidence the diagnosis rests on.",
                evaluation_mode="evidentiary",
                required=True,
            ),
            ReasoningCriterion(
                criterion_id="elegance",
                instruction="Prefer the simplest sufficient explanation.",
                evaluation_mode="judgment",
                required=False,
            ),
        ],
    )


class _StubProgram:
    """A deterministic stand-in, so the harness is testable without an LM."""

    program_id = "diagnose"
    program_version = "1.0"

    def __init__(self, *, evidence: list[str] | None = None, diagnosis: str = "label noise"):
        self.evidence = ["exp-1"] if evidence is None else evidence
        self.diagnosis = diagnosis

    def respond(self, packet, *, experiment_ids):
        return {
            "review_id": f"{self.program_id}-{packet.diagnostic_packet_id}",
            "primary_diagnosis": self.diagnosis,
            "diagnosis_confidence": 0.6,
            "recommended_next_action": "run_error_analysis",
            "expected_value": "resolves whether labels bound accuracy",
            "supporting_evidence": self.evidence,
            "evidence_references": self.evidence,
            "experiment_ids": experiment_ids,
        }


def test_a_program_runs_through_the_ordinary_provider_path(packet, profile) -> None:
    provider = ReasoningScientistProvider(profile, _StubProgram())

    review = provider.review(packet, experiment_ids=["exp-1"])

    # Normalisation attached provider-owned traceability rather than trusting the program.
    assert review.project_id == "project-1"
    assert review.provider_profile_id == "reasoning-1"
    assert review.raw_response_artifact is not None
    assert review.primary_diagnosis == "label noise"


def test_a_grounded_review_satisfies_the_rubric(packet, profile, rubric) -> None:
    provider = ReasoningScientistProvider(profile, _StubProgram())
    review = provider.review(packet)

    score = score_review(
        review,
        rubric,
        EvaluationCase(
            case_id="c1",
            diagnostic_packet_id="packet-1",
            project_id="project-1",
            expected_evidence_refs=["exp-1"],
        ),
    )

    assert score.passed is True


def test_an_ungrounded_review_fails_the_rubric(packet, profile, rubric) -> None:
    provider = ReasoningScientistProvider(profile, _StubProgram(evidence=[]))
    review = provider.review(packet)

    score = score_review(
        review,
        rubric,
        EvaluationCase(
            case_id="c1",
            diagnostic_packet_id="packet-1",
            project_id="project-1",
        ),
    )

    assert score.passed is False
    assert "not grounded" in (score.criteria[0].detail or "")


def test_ignoring_available_evidence_fails(packet, profile, rubric) -> None:
    provider = ReasoningScientistProvider(profile, _StubProgram(evidence=["unrelated"]))
    review = provider.review(packet)

    score = score_review(
        review,
        rubric,
        EvaluationCase(
            case_id="c1",
            diagnostic_packet_id="packet-1",
            project_id="project-1",
            expected_evidence_refs=["exp-1"],
        ),
    )

    assert score.passed is False


def test_judgment_criteria_are_recorded_but_never_guessed(packet, profile, rubric) -> None:
    """Scoring a judgment criterion heuristically would report a number nobody measured."""
    provider = ReasoningScientistProvider(profile, _StubProgram())
    review = provider.review(packet)

    score = score_review(
        review,
        rubric,
        EvaluationCase(
            case_id="c1",
            diagnostic_packet_id="packet-1",
            project_id="project-1",
        ),
    )
    elegance = next(item for item in score.criteria if item.criterion_id == "elegance")

    assert elegance.required is False
    assert "not machine-checkable" in (elegance.detail or "")


def test_evaluation_reports_a_pass_rate_over_a_dataset(packet, profile, rubric) -> None:
    evaluator = ProgramEvaluator(rubric)
    program = _StubProgram()
    provider = ReasoningScientistProvider(profile, program)
    cases = [
        EvaluationCase(case_id=f"c{index}", diagnostic_packet_id="packet-1", project_id="project-1")
        for index in range(4)
    ]

    result = evaluator.evaluate(program, provider, cases, {"packet-1": packet})

    assert result.case_count == 4
    assert result.pass_rate == 1.0


def test_a_missing_packet_is_an_error_not_a_pass(packet, profile, rubric) -> None:
    evaluator = ProgramEvaluator(rubric)
    program = _StubProgram()
    provider = ReasoningScientistProvider(profile, program)
    cases = [EvaluationCase(case_id="c1", diagnostic_packet_id="absent", project_id="project-1")]

    result = evaluator.evaluate(program, provider, cases, {})

    assert result.pass_rate == 0.0
    assert result.scores[0].error is not None


def test_one_failing_case_does_not_abort_the_run(packet, profile, rubric) -> None:
    class _Exploding(_StubProgram):
        def respond(self, packet, *, experiment_ids):
            raise RuntimeError("program blew up")

    evaluator = ProgramEvaluator(rubric)
    program = _Exploding()
    provider = ReasoningScientistProvider(profile, program)
    cases = [EvaluationCase(case_id="c1", diagnostic_packet_id="packet-1", project_id="project-1")]

    result = evaluator.evaluate(program, provider, cases, {"packet-1": packet})

    assert result.scores[0].error == "program blew up"
    assert result.pass_rate == 0.0
