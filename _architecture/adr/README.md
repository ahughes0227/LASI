# Architecture Decision Records

Short records of decisions that shaped LASI, written so a decision does not have
to be re-argued every time the architecture is reread.

An ADR records **what was decided and why**, plus the conditions that would
justify revisiting it. It is not a design document. Designs belong in the
numbered `_architecture/NN_*.md` documents, and per the repository constraint no
new architecture document is added without a passing test exercising what it
describes. ADRs are the exception: they record decisions, not designs.

| ADR | Decision |
|---|---|
| [ADR-001](001-terminology.md) | Capability, component, and belief terminology |
| [ADR-002](002-search-versus-ranking.md) | Symbolic layer owns legality; learned layer owns ranking |
| [ADR-003](003-postgresql-pgvector.md) | PostgreSQL + pgvector as the single store |
| [ADR-004](004-mlflow-observability.md) | MLflow as trace and experiment spine |
| [ADR-005](005-dspy-optimization.md) | DSPy for reasoning-capability optimization, challenger-only |
| [ADR-006](006-operating-surface.md) | Operating surface: OpenCode vs. Python CLI (open) |
| [ADR-007](007-execution-runtime.md) | Execution runtime: no LangGraph, no Temporal |
| [ADR-008](008-copier-scaffolding.md) | Copier as the single scaffolding mechanism |

## Status values

`proposed` · `accepted` · `open` · `superseded by ADR-NNN`
