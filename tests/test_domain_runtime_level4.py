import json
from pathlib import Path
from typing import Any

from services.benchmarks import DomainRuntimeEvaluator

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/domain_runtime"
EVALUATOR = DomainRuntimeEvaluator(ROOT)


def _result(case_id: str):
    return EVALUATOR.evaluate_file(FIXTURES / f"{case_id}.json")


def _stable_plan(plan: Any) -> dict[str, Any]:
    value = plan.model_dump(mode="json")
    value["plan_id"] = "<plan>"
    for step in value["steps"]:
        step["step_id"] = "<step>"
    return value


def test_read_only_mismatch() -> None:
    assert _result("read_only_mismatch").passed


def test_modify_high_confidence() -> None:
    result = _result("modify_high_confidence")
    assert result.passed, result.failures
    assert result.plan.steps[1].side_effect_class == "update"
    assert result.plan.steps[1].validation_capability_ids == ["evaluation"]


def test_modify_low_confidence() -> None:
    result = _result("modify_low_confidence")
    assert result.passed, result.failures
    assert result.plan.status == "blocked"


def test_conflicting_authority() -> None:
    result = _result("conflicting_authority")
    assert result.passed, result.failures
    assert any(
        "Conflicting authorities" in item.reason for item in result.plan.rejected_capabilities
    )


def test_unreachable_goal() -> None:
    result = _result("unreachable_goal")
    assert result.passed, result.failures


def test_fixtures_do_not_contain_workflow_graphs() -> None:
    forbidden_keys = {"nodes", "workflow", "workflow_id", "task_type", "dependencies"}
    for path in sorted(FIXTURES.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert not forbidden_keys.intersection(value), path.name


def test_evaluator_reports_all_expectation_failures(tmp_path: Path) -> None:
    value = json.loads((FIXTURES / "read_only_mismatch.json").read_text(encoding="utf-8"))
    value["expected_status"] = "blocked"
    value["expected_capability_ids"] = ["research"]
    value["expected_unresolved_predicate_indexes"] = [0]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    result = EVALUATOR.evaluate_file(path)
    assert not result.passed
    assert len(result.failures) >= 3


def test_all_level4_cases_are_deterministic_across_ten_runs() -> None:
    for path in sorted(FIXTURES.glob("*.json")):
        plans = [_stable_plan(EVALUATOR.evaluate_file(path).plan) for _ in range(10)]
        assert all(plan == plans[0] for plan in plans), path.name


def test_level4_cases_do_not_write_repository_state() -> None:
    before = {path: path.stat().st_mtime_ns for path in ROOT.glob("services/**/*.py")}
    for path in sorted(FIXTURES.glob("*.json")):
        EVALUATOR.evaluate_file(path)
    after = {path: path.stat().st_mtime_ns for path in before}
    assert before == after
