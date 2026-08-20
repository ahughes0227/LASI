"""Golden and state coverage for fixed static report rendering."""

from pathlib import Path

import pytest
from services.contracts import StaticReportData
from services.reports import ImmutableReportError, ReportRenderer

_ROOT = Path(__file__).parent
_GOLDEN = _ROOT / "fixtures" / "reports" / "minimal_report.golden"
_SECTION_NAMES = (
    "executive_summary",
    "current_decision",
    "dataset_summary",
    "dataset_characterization",
    "eda_findings",
    "surprising_findings",
    "proposed_approaches",
    "experiment_summary",
    "experiments_tried",
    "results_and_interpretation",
    "model_comparison",
    "performance_gap_diagnosis",
    "learning_curves",
    "error_analysis",
    "cluster_or_latent_analysis",
    "scientist_review",
    "scientific_criticism",
    "decision_record",
    "knowledge_context",
    "recommendation",
    "project_outcome",
    "token_telemetry",
    "appendix",
)


def _report(**overrides: object) -> StaticReportData:
    section = {
        "section_status": "not_run",
        "missing_or_blocked_reason": "The minimal golden fixture did not run this section.",
    }
    values: dict[str, object] = {
        "report_id": "report-golden-1",
        "report_header": {"title": "Golden Report", "project_id": "project-1"},
        "project_outcome_status": "pending",
        "provenance": {"source_records": ["db://report-1"], "source_artifacts": ["mlflow://run-1"]},
    }
    values.update({name: section for name in _SECTION_NAMES})
    values.update(overrides)
    return StaticReportData.model_validate(values)


def test_fixed_template_matches_golden() -> None:
    rendered = ReportRenderer().render(_report())
    for expected in _GOLDEN.read_text(encoding="utf-8").splitlines():
        assert expected in rendered
    assert rendered.count('<section class="report-section"') == 22


@pytest.mark.parametrize(
    "status", ["blocked_by_privacy", "failed", "partial_success", "deferred_to_later_phase"]
)
def test_non_complete_states_are_visible(status: str) -> None:
    report = _report(
        learning_curves={
            "section_status": status,
            "missing_or_blocked_reason": "Evidence unavailable",
        }
    )
    rendered = ReportRenderer().render(report)
    assert status.replace("_", " ") in rendered
    assert "Evidence unavailable" in rendered


def test_renderer_rejects_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "report.html"
    renderer = ReportRenderer()
    renderer.write_immutable(_report(), path)
    with pytest.raises(ImmutableReportError):
        renderer.write_immutable(_report(), path)


def test_rendering_escapes_structured_values() -> None:
    rendered = ReportRenderer().render(
        _report(executive_summary={"section_status": "complete", "summary": "<unsafe>"})
    )
    assert "&lt;unsafe&gt;" in rendered
