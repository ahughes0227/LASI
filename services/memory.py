"""Authoritative SQL context and asynchronously rebuilt Graphiti projection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .contracts import Belief, Evidence, MemoryContext, ProjectionStatus, RunSummary
from .ledger import AuthorityStore


class SemanticProjection(Protocol):
    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]: ...

    async def project(self, envelope: dict[str, Any]) -> None: ...


class InMemoryProjection:
    def __init__(self, beliefs: tuple[Belief, ...] = ()) -> None:
        self.beliefs = list(beliefs)
        self.events: list[dict[str, Any]] = []
        self.fail = False

    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]:
        if self.fail:
            raise RuntimeError("projection unavailable")
        terms = {part.lower() for part in query.split()}
        ranked = sorted(
            (item for item in self.beliefs if item.project_id == project_id),
            key=lambda item: len(terms & set(item.statement.lower().split())),
            reverse=True,
        )
        return tuple(ranked[:limit])

    async def project(self, envelope: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("projection unavailable")
        self.events.append(envelope)


class GraphitiProjection:
    def __init__(self, client: Any, *, belief_decoder: Callable[[Any, str], Belief | None]) -> None:
        self.client = client
        self.belief_decoder = belief_decoder

    async def retrieve(self, project_id: str, query: str, *, limit: int) -> tuple[Belief, ...]:
        results = await self.client.search(query, group_ids=[project_id], num_results=limit)
        decoded = (self.belief_decoder(result, project_id) for result in results)
        return tuple(item for item in decoded if item is not None)

    async def project(self, envelope: dict[str, Any]) -> None:
        from graphiti_core.nodes import EpisodeType

        await self.client.add_episode(
            name=str(envelope["kind"]),
            episode_body=__import__("json").dumps(envelope, sort_keys=True),
            source=EpisodeType.json,
            source_description="LASI authority event",
            reference_time=__import__("datetime").datetime.fromisoformat(
                str(envelope["occurred_at"])
            ),
            group_id=str(envelope["project_id"]),
            uuid=str(envelope["event_id"]),
        )


class ProjectionWorker:
    def __init__(self, store: AuthorityStore, projection: SemanticProjection) -> None:
        self.store = store
        self.projection = projection

    async def drain_once(self, limit: int = 100) -> int:
        processed = 0
        for envelope in self.store.outbox_batch(limit):
            sequence = int(envelope["sequence"])
            try:
                await self.projection.project(envelope)
            except Exception as exc:
                self.store.mark_projection_failed(
                    sequence, int(envelope["attempts"]) + 1, f"{type(exc).__name__}: {exc}"
                )
            else:
                self.store.mark_projected(sequence)
            processed += 1
        return processed


class MemoryService:
    def __init__(self, store: AuthorityStore, projection: SemanticProjection) -> None:
        self.store = store
        self.projection = projection

    def add_evidence(self, evidence: Evidence) -> None:
        self.store.add_evidence(evidence)

    def add_run_summary(self, summary: RunSummary) -> None:
        self.store.add_run_summary(summary)

    async def context(
        self,
        *,
        project_id: str,
        query: str,
        constraints: tuple[str, ...] = (),
        limit: int = 20,
    ) -> MemoryContext:
        health = self.store.projection_health()
        warnings: list[str] = []
        try:
            beliefs = await self.projection.retrieve(project_id, query, limit=limit)
        except Exception as exc:
            beliefs = ()
            warnings.append(f"semantic_projection_unavailable:{type(exc).__name__}")
            health = health.model_copy(
                update={
                    "status": ProjectionStatus.DEGRADED,
                    "last_error": f"{type(exc).__name__}: {exc}",
                }
            )
        return MemoryContext(
            project_id=project_id,
            beliefs=beliefs,
            evidence=self.store.evidence(project_id),
            recent_runs=self.store.run_summaries(project_id, limit),
            constraints=constraints,
            authoritative_sequence=health.authoritative_sequence,
            projection=health,
            retrieval_warnings=tuple(warnings),
        )
