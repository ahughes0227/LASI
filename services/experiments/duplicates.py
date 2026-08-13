"""Interfaces for deterministic duplicate-experiment detection."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from services.contracts import ExperimentPlan


@dataclass(frozen=True)
class DuplicateMatch:
    experiment_id: str
    fingerprint: str
    status: str
    reason: str


class DuplicateExperimentDetector:
    """Fingerprint plans and query prior records; policy decides whether to rerun."""

    @staticmethod
    def fingerprint(plan: ExperimentPlan) -> str:
        basis = {
            "project_id": plan.project_id,
            "dataset_version": plan.dataset_version,
            "hypothesis": plan.hypothesis,
            "experiment_type": plan.experiment_type,
            "execution_backend": plan.execution_backend,
            "remote_host_profile": plan.remote_host_profile,
            "privacy_mode": plan.privacy_mode,
            "planned_tool_runs": [
                run.model_dump(mode="json", exclude_none=True) for run in plan.planned_tool_runs
            ],
            "expected_artifacts": sorted(plan.expected_artifacts),
        }
        payload = json.dumps(basis, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def find_duplicate(
        self, plan: ExperimentPlan, prior: Iterable[tuple[str, ExperimentPlan, str]]
    ) -> DuplicateMatch | None:
        target = self.fingerprint(plan)
        for experiment_id, prior_plan, status in prior:
            if self.fingerprint(prior_plan) == target:
                return DuplicateMatch(
                    experiment_id=experiment_id,
                    fingerprint=target,
                    status=status,
                    reason="equivalent plan on the same dataset and execution conditions",
                )
        return None
