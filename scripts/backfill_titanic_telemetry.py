"""Backfill the Titanic demonstration's omitted action telemetry from durable evidence.

This is a one-time migration for runs completed before component workflows wrote
their own operational-memory ledger. It never estimates tokens: local actions
are ``not_applicable`` and prior agent reasoning without a usage receipt is
``not_available``.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.context import ArtifactContract, ICMStore
from services.contracts import ProjectConfig
from services.contracts.models import PrivacyMode
from services.memory import (
    ActionUsage,
    Base,
    OperationalMemory,
    create_engine,
    create_session_factory,
)
from services.telemetry import TokenUsageService

PROJECT_ID = "kaggle-titanic-naive"
VARIANTS: dict[str, dict[str, int | str]] = {
    "naive": {"experiment": "titanic-naive-logistic-v1", "components": 4, "submission": "55470945"},
    "title-family": {
        "experiment": "titanic-title-family-logistic-v1",
        "components": 5,
        "submission": "55470993",
    },
}


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    store = ICMStore(repository_root)
    project_root = store.project_root(PROJECT_ID)
    database = project_root / "artifacts" / "operational.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    memory = OperationalMemory(create_session_factory(engine))
    if not memory.project_exists(PROJECT_ID):
        project = ProjectConfig(
            project_id=PROJECT_ID,
            project_name="Kaggle Titanic full LASI demonstration",
            problem_type="binary_classification",
            modality="tabular",
            privacy_mode=PrivacyMode.LOCAL_ONLY,
        )
        from services.memory import Project

        memory.add(
            Project(
                project_id=project.project_id,
                project_name=project.project_name,
                problem_type=project.problem_type,
                modality=project.modality,
                payload=project.model_dump(mode="json"),
            )
        )
    metering = TokenUsageService(memory)
    for variant, details in VARIANTS.items():
        _backfill_variant(metering, memory, project_root, variant, details)
    _record_not_available(
        metering,
        memory,
        "legacy-agent-feedback-decision",
        "agent_reasoning",
        "codex-desktop",
        "unreported",
        "the pre-telemetry agent runtime did not provide an authoritative token receipt",
    )
    _write_projection(store, metering)


def _backfill_variant(
    metering: TokenUsageService,
    memory: OperationalMemory,
    project_root: Path,
    variant: str,
    details: dict[str, int | str],
) -> None:
    experiment_id = str(details["experiment"])
    metrics_path = project_root / "30_evidence" / "metrics" / f"{experiment_id}.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"missing evidence for telemetry migration: {metrics_path}")
    json.loads(metrics_path.read_text(encoding="utf-8"))
    prefix = f"legacy-{experiment_id}"
    for action_type in (
        "component_spec_resolution",
        "experiment_plan_compilation",
        "decision_evaluation",
    ):
        _record_not_applicable(metering, memory, f"{prefix}-{action_type}", action_type)
    for ordinal in range(int(details["components"])):
        _record_not_applicable(
            metering, memory, f"{prefix}-component-{ordinal + 1}", "component_execution"
        )
    for action_type in ("project_context_update", "artifact_persistence", "submission_validation"):
        _record_not_applicable(metering, memory, f"{prefix}-{action_type}", action_type)
    _record_not_applicable(
        metering,
        memory,
        f"legacy-kaggle-submission-{details['submission']}",
        "external_benchmark_submission",
    )
    _record_not_available(
        metering,
        memory,
        f"legacy-agent-submit-{variant}",
        "agent_orchestration",
        "codex-desktop",
        "unreported",
        "the pre-telemetry agent runtime did not provide an authoritative token receipt",
    )


def _record_not_applicable(
    metering: TokenUsageService, memory: OperationalMemory, action_id: str, action_type: str
) -> None:
    usage_id = f"usage-{action_id}"
    if memory.get(ActionUsage, usage_id) is None:
        metering.record_not_applicable(
            project_id=PROJECT_ID,
            action_id=action_id,
            action_type=action_type,
            reason="reconstructed local or CLI action did not invoke a token-metered runtime",
        )


def _record_not_available(
    metering: TokenUsageService,
    memory: OperationalMemory,
    action_id: str,
    action_type: str,
    provider_profile_id: str,
    model_name: str,
    reason: str,
) -> None:
    usage_id = f"usage-{action_id}"
    if memory.get(ActionUsage, usage_id) is None:
        metering.record_provider_action(
            project_id=PROJECT_ID,
            action_id=action_id,
            action_type=action_type,
            provider_profile_id=provider_profile_id,
            model_name=model_name,
            usage=None,
        )


def _write_projection(store: ICMStore, metering: TokenUsageService) -> None:
    summary = metering.project_report(PROJECT_ID)
    records = metering.action_records(PROJECT_ID)
    document = {
        "project_id": PROJECT_ID,
        "authoritative_source": "artifacts/operational.sqlite:action_usage",
        "migration": "backfilled_from_durable_project_evidence",
        "summary": {
            **summary.model_dump(mode="json"),
        },
        "actions": [
            {
                "action_id": record.action_id,
                "action_type": record.action_type,
                "status": record.metering_status,
                "total_tokens": record.total_tokens,
                "reason": record.unavailable_reason,
            }
            for record in records
        ],
    }
    contract = ArtifactContract(
        capability="telemetry",
        writes=["30_evidence/telemetry/action-usage.json"],
    )
    store.write_artifact(
        PROJECT_ID,
        "30_evidence/telemetry/action-usage.json",
        json.dumps(document, indent=2, sort_keys=True),
        overwrite=True,
        contract=contract,
    )


if __name__ == "__main__":
    main()
