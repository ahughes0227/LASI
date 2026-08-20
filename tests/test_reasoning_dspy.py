"""The DSPy path, end to end, without a live model.

Gated on the optional extra rather than mocked away: a test that stubbed DSPy out would
prove only that the stub works. `DummyLM` runs the real signature, adapter, and module.
"""

import pytest
from services.contracts import ProviderProfile
from services.contracts.models import DiagnosticPacket, PrivacyMode
from services.reasoning import ReasoningScientistProvider, package_hash

dspy = pytest.importorskip("dspy", reason="needs the optional 'dspy' extra")

from dspy.utils.dummies import DummyLM  # noqa: E402
from services.reasoning.optimization import (  # noqa: E402
    DspyReasoningProgram,
    build_signature,
)

pytestmark = pytest.mark.dspy

RESPONSE = {
    "primary_diagnosis": "label noise bounds achievable accuracy",
    "recommended_next_action": "run_error_analysis",
    "supporting_evidence": "exp-1, exp-2",
}


@pytest.fixture
def packet() -> DiagnosticPacket:
    return DiagnosticPacket(
        diagnostic_packet_id="packet-1",
        project_id="project-1",
        problem_type="classification",
        dataset_version_id="dv-1",
        current_project_state="accuracy plateaus at 0.70",
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
def program() -> DspyReasoningProgram:
    dspy.configure(lm=DummyLM([RESPONSE] * 8))
    return DspyReasoningProgram("diagnose", "1.0")


def test_the_signature_names_the_allowed_actions() -> None:
    """Optimisation must target the vocabulary the provider layer enforces."""
    instructions = build_signature().instructions

    assert "run_error_analysis" in instructions
    assert "collect_more_data" in instructions


def test_a_dspy_program_produces_a_valid_review(
    program: DspyReasoningProgram, profile: ProviderProfile, packet: DiagnosticPacket
) -> None:
    provider = ReasoningScientistProvider(profile, program)

    review = provider.review(packet, experiment_ids=["exp-1"])

    assert review.primary_diagnosis == RESPONSE["primary_diagnosis"]
    assert review.recommended_next_action == "run_error_analysis"
    # The comma-separated field became real references.
    assert review.evidence_references == ["exp-1", "exp-2"]
    # Provider-owned traceability was attached by normalisation, not by the program.
    assert review.provider_profile_id == "reasoning-1"
    assert review.raw_response_artifact is not None


def test_a_program_artifact_is_hashable_and_binds_approval(
    program: DspyReasoningProgram,
) -> None:
    """Approval binds to this hash, so it must cover what the program actually is."""
    artifact = program.artifact()

    assert artifact["program_id"] == "diagnose"
    assert "state" in artifact
    assert package_hash(artifact) == package_hash(program.artifact())


def test_changing_the_program_changes_its_hash(program: DspyReasoningProgram) -> None:
    """Otherwise an approval for one build would silently authorise another."""
    before = package_hash(program.artifact())
    program.module.demos = [{"evidence": "x", "primary_diagnosis": "y"}]

    assert package_hash(program.artifact()) != before
