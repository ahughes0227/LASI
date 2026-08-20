# ADR-003: PostgreSQL + pgvector as the single store

**Status:** accepted

## Context

LASI's operational memory is SQLite (`lasi.db`, 35 tables, 8 Alembic revisions).
Planner candidate retrieval uses `PlannerVectorIndex`, a TF-IDF index over the
planner catalog persisted to disk. Episode retrieval (ADR-002's learned ranking)
needs similarity search over accumulated history.

The obvious failure mode is acquiring a separate relational store, vector store,
graph store, and document store. LASI's architecture already resists this:
typed nodes and edges supply associative retrieval inside the same database.

## Decision

Migrate operational memory to **PostgreSQL**, and use **pgvector** for
similarity search within it. Do not introduce a separate vector database, graph
database, or document store.

Sequencing matters:

1. Postgres first, as a straight backend swap. `LASI_DATABASE_URL` is already
   honored; columns are generic `JSON`/`Text`; `UTCDateTime` normalizes to naive
   UTC. Keep SQLite working for unit tests.
2. The existing 8 revisions must run clean against Postgres in CI before any new
   revision is added.
3. pgvector arrives only when episode retrieval exists to consume it, replacing
   `PlannerVectorIndex` *behind its current interface*. TF-IDF remains the
   fallback until embedding retrieval measurably wins on the same fixture set.

### pgvector is provisioned but deliberately not adopted

The database runs on the `pgvector/pgvector` image and CI asserts the extension is
available, so adopting it will need no second datastore and no infrastructure change.
No column uses it.

Two things have to exist first. There is no embedding producer until the reasoning
capability layer lands (ADR-005), and this decision made adoption conditional on
embedding retrieval *measurably* beating the incumbent — which cannot be measured
without one. Episode retrieval currently matches on a structural fingerprint of the
goal's predicates, which needs no embeddings at all and is exact rather than
approximate.

Adding a vector column now would be a schema commitment with nothing to write into it,
and would pre-judge a comparison that has not been run. The trigger for revisiting is
concrete: an embedding producer exists, and embedding retrieval beats fingerprint
matching on the same fixture set.

## Consequences

- Migrating at 8 revisions is cheap; at 20 it is not. This is the reason to do
  it before the episode and ranking tables land.
- Postgres activates a latent defect: `lease_ready_task` had no row locking, and
  SQLite was hiding it by serialising writes. Fixed with
  `.with_for_update(skip_locked=True)` alongside this migration rather than after it,
  since the move is what makes the race reachable. See ADR-007.
- `alembic/env.py` read only the ini file, so migrations ran against the developer's
  local SQLite database whatever `LASI_DATABASE_URL` said. Pointing Alembic at
  PostgreSQL was impossible without editing tracked configuration; it now honours the
  same variable the application does.
- Concurrency becomes real rather than theoretical, which means the runtime's
  fan-out behavior needs tests it does not currently have.
- A Postgres service is required for local development, so `docker-compose.yml`
  becomes a real dependency of the workflow rather than a convenience.
- pgvector must not become a second source of truth. Embeddings are derived
  data, rebuildable from the relational tables, exactly as `PlannerVectorIndex`
  is rebuildable today.
