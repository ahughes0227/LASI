# LASI

LASI is a memory-informed, governed ML research runtime. An LLM planner proposes
strict operator plans from retrieved temporal memory. A deterministic policy kernel
checks identity, evidence, risk, dependencies, and approvals before a rigid executor
can act.

    Graphiti memory -> exploration policy -> LangChain planner
                    -> verifier -> LangGraph interrupt/execution -> SQL ledger

Graphiti is semantic memory, not authority. LangGraph is orchestration, not policy.
LangChain is planner composition, not an execution sandbox.

Development:

    uv sync --group dev
    uv run pytest

Start with _architecture/00_LASI_OVERVIEW.md and
_architecture/01_ARCHITECTURE.md.
