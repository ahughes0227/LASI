from __future__ import annotations

import asyncio

from services.contracts import Evidence, ProjectionStatus
from services.memory import InMemoryProjection, MemoryService, ProjectionWorker


def test_projection_outage_never_blocks_authoritative_context(core) -> None:
    async def scenario():
        projection = InMemoryProjection()
        memory = MemoryService(core.store, projection)
        memory.add_evidence(
            Evidence(
                evidence_id="e-1",
                project_id="project-1",
                source="human",
                content="durable",
            )
        )
        projection.fail = True
        context = await memory.context(project_id="project-1", query="durable")
        assert context.evidence[0].content == "durable"
        assert context.projection.status == ProjectionStatus.DEGRADED
        projection.fail = False
        assert await ProjectionWorker(core.store, projection).drain_once() > 0
        return projection

    projection = asyncio.run(scenario())
    assert projection.events
