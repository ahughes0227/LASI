# LASI

LASI is a memory-informed, governed ML research runtime. An LLM planner proposes
strict operator plans from retrieved temporal memory. A deterministic policy kernel
checks identity, evidence, risk, dependencies, and approvals before a rigid executor
can act.

    SQL + Graphiti memory -> exploration policy -> LiteLLM planner
                    -> verifier -> LangGraph interrupt/execution -> SQL ledger

Graphiti is semantic memory, not authority. LangGraph is orchestration, not policy.
LiteLLM is provider routing, not an execution surface. Every executable action is a
registered, versioned operator launched in a separate process after deterministic
authorization.

Development:

    uv sync --group dev
    uv run ruff check services tests
    uv run mypy services
    uv run pytest -q

The core suite is offline. It uses a fake planner and an in-memory semantic projection;
live model and Neo4j integration are deployment concerns rather than test prerequisites.

For the supported Graphiti backend, copy `.env.example` to `.env`, replace the
password, and run `docker compose up -d neo4j`. The service binds only to localhost;
Graphiti connects over `bolt://localhost:7687`.

Start with _architecture/00_LASI_OVERVIEW.md and
_architecture/01_ARCHITECTURE.md.
