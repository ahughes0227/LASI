"""Authoritative operational memory plus replaceable semantic projections."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .contracts import Belief, Evidence, LedgerEvent, MemoryContext, RunSummary
from .ledger import SqliteLedger


class SemanticProjection(Protocol):
    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]: ...

    async def project(self, event: LedgerEvent) -> None: ...


class InMemoryProjection:
    def __init__(self, beliefs: tuple[Belief, ...] = ()) -> None:
        self.beliefs = list(beliefs)
        self.events: list[LedgerEvent] = []

    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]:
        terms = {part.lower() for part in query.split()}
        ranked = sorted(
            (item for item in self.beliefs if item.project_id == project_id),
            key=lambda item: len(terms & set(item.statement.lower().split())),
            reverse=True,
        )
        return tuple(ranked[:limit])

    async def project(self, event: LedgerEvent) -> None:
        self.events.append(event)


class GraphitiProjection:
    """Graphiti temporal retrieval adapter; it never grants authority."""

    def __init__(
        self, client: Any, *, belief_decoder: Callable[[Any, str], Belief | None]
    ) -> None:
        self.client = client
        self.belief_decoder = belief_decoder

    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]:
        results = await self.client.search(query, group_ids=[project_id], num_results=limit)
        beliefs = (self.belief_decoder(result, project_id) for result in results)
        return tuple(item for item in beliefs if item is not None)

    async def project(self, event: LedgerEvent) -> None:
        from graphiti_core.nodes import EpisodeType

        await self.client.add_episode(
            name=event.kind,
            episode_body=event.model_dump_json(),
            source=EpisodeType.json,
            source_description="LASI authoritative ledger event",
            reference_time=event.occurred_at,
            group_id=event.project_id,
        )


class MemoryService:
    def __init__(self, ledger: SqliteLedger, projection: SemanticProjection) -> None:
        self.ledger = ledger
        self.projection = projection
        self._evidence: dict[str, Evidence] = {}
        self._runs: list[RunSummary] = []
        self._projected_event_ids: set[str] = set()

    def add_evidence(self, evidence: Evidence) -> None:
        self._evidence[evidence.evidence_id] = evidence
        self.ledger.emit(
            evidence.project_id, "evidence_observed", evidence.model_dump(mode="json")
        )

    def add_run_summary(self, summary: RunSummary, project_id: str) -> None:
        self._runs.append(summary)
        self.ledger.emit(project_id, "run_summarized", summary.model_dump(mode="json"))

    async def context(
        self,
        *,
        project_id: str,
        query: str,
        constraints: tuple[str, ...] = (),
        limit: int = 20,
    ) -> MemoryContext:
        beliefs = await self.projection.retrieve(project_id, query, limit=limit)
        return MemoryContext(
            project_id=project_id,
            beliefs=beliefs,
            evidence=tuple(
                item for item in self._evidence.values() if item.project_id == project_id
            ),
            recent_runs=tuple(self._runs[-limit:]),
            constraints=constraints,
        )

    async def project_new_events(self, project_id: str) -> None:
        for event in self.ledger.recent_events(project_id):
            if event.event_id not in self._projected_event_ids:
                await self.projection.project(event)
                self._projected_event_ids.add(event.event_id)
