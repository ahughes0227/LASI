"""Pure projections from reconstructed project state into domain facts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from services.context.models import ProjectState

from .models import DomainFact, DomainStateSnapshot

_CLAIM_STATUS = {
    "unsupported": "inferred",
    "weak": "inferred",
    "conflicting": "conflicting",
    "supported": "observed",
    "strongly_supported": "verified",
    "invalidated": "invalidated",
}
_CONFIDENCE = {"low": 0.25, "medium": 0.5, "high": 0.8}


class DomainStateProjector:
    """Project existing ICM state without reading or mutating any persistence."""

    def project_project_state(
        self,
        state: ProjectState,
        *,
        revision: int,
        created_at: datetime,
    ) -> DomainStateSnapshot:
        facts: list[DomainFact] = []
        project_ref = f"icm://projects/{state.project_id}/10_context/current_state.md"

        self._add_optional(
            facts,
            state,
            subject="project",
            predicate="objective",
            value=state.objective,
            status="observed",
            confidence=1.0,
            authority=100,
            evidence_ref=project_ref,
            observed_at=created_at,
        )
        self._add_optional(
            facts,
            state,
            subject="project",
            predicate="constraints",
            value=state.constraints,
            status="observed",
            confidence=1.0,
            authority=100,
            evidence_ref=project_ref,
            observed_at=created_at,
        )

        for experiment in sorted(state.experiments, key=lambda item: item.experiment_id):
            experiment_ref = (
                f"icm://projects/{state.project_id}/20_work/experiments/{experiment.experiment_id}"
            )
            self._add(
                facts,
                state.project_id,
                subject=f"experiment:{experiment.experiment_id}",
                predicate="status",
                value=experiment.status,
                status="observed",
                confidence=1.0,
                authority=90,
                evidence_ref=experiment_ref,
                observed_at=created_at,
            )
            self._add(
                facts,
                state.project_id,
                subject=f"experiment:{experiment.experiment_id}",
                predicate="hypothesis",
                value=experiment.hypothesis,
                status="observed",
                confidence=1.0,
                authority=70,
                evidence_ref=experiment_ref,
                observed_at=created_at,
            )

        for claim in sorted(state.claims, key=lambda item: item.claim_id):
            claim_status = _CLAIM_STATUS[str(claim.status)]
            claim_confidence = _CONFIDENCE.get(claim.confidence, 0.0)
            claim_ref = (
                f"icm://projects/{state.project_id}/30_evidence/claims/{claim.claim_id}.yaml"
            )
            subject = f"claim:{claim.claim_id}"
            self._add(
                facts,
                state.project_id,
                subject=subject,
                predicate="statement",
                value=claim.claim,
                status=claim_status,
                confidence=claim_confidence,
                authority=60,
                evidence_ref=claim_ref,
                observed_at=created_at,
            )
            self._add(
                facts,
                state.project_id,
                subject=subject,
                predicate="status",
                value=str(claim.status),
                status=claim_status,
                confidence=claim_confidence,
                authority=80,
                evidence_ref=claim_ref,
                observed_at=created_at,
            )
            for dependency_id in sorted(set(claim.depends_on_claim_ids)):
                self._add(
                    facts,
                    state.project_id,
                    subject=subject,
                    predicate="depends_on",
                    value=dependency_id,
                    status="inferred",
                    confidence=claim_confidence,
                    authority=60,
                    evidence_ref=claim_ref,
                    observed_at=created_at,
                    id_suffix=dependency_id,
                )

        self._add_optional(
            facts,
            state,
            subject="project",
            predicate="recommendation",
            value=state.recommendation,
            status="inferred",
            confidence=0.5,
            authority=40,
            evidence_ref=project_ref,
            observed_at=created_at,
        )
        facts.sort(key=lambda fact: fact.fact_id)
        return DomainStateSnapshot(
            project_id=state.project_id,
            revision=revision,
            facts=facts,
            created_at=created_at,
        )

    @staticmethod
    def _safe_part(value: str) -> str:
        return re.sub(r"[/: ]", "_", value)

    @classmethod
    def _fact_id(
        cls, project_id: str, subject: str, predicate: str, id_suffix: str | None = None
    ) -> str:
        fact_id = f"domain-fact:{project_id}:{cls._safe_part(subject)}:{cls._safe_part(predicate)}"
        if id_suffix is not None:
            fact_id += f":{cls._safe_part(id_suffix)}"
        return fact_id

    @classmethod
    def _add_optional(cls, facts: list[DomainFact], state: ProjectState, **kwargs: Any) -> None:
        if kwargs["value"] is not None and str(kwargs["value"]).strip():
            cls._add(facts, state.project_id, **kwargs)

    @classmethod
    def _add(cls, facts: list[DomainFact], project_id: str, **kwargs: Any) -> None:
        id_suffix = cast(str | None, kwargs.pop("id_suffix", None))
        subject = str(kwargs["subject"])
        predicate = str(kwargs["predicate"])
        evidence_ref = kwargs.pop("evidence_ref")
        facts.append(
            DomainFact(
                fact_id=cls._fact_id(project_id, subject, predicate, id_suffix),
                project_id=project_id,
                source="project_state",
                evidence_refs=[str(evidence_ref)],
                **kwargs,
            )
        )
