# AGENTS.md

LASI is a governed ML research runtime:

    memory -> exploration pressure -> LLM plan -> deterministic verification
           -> rigid execution -> evidence -> memory

Before architectural changes, read architecture documents 00 through 08 in numeric
order and _core/glossary.md.

## Non-negotiable boundaries

- SQL records what happened and what was authorized.
- Artifact storage records what was produced.
- Graphiti is a rebuildable temporal semantic projection.
- The LLM planner recommends only typed Plan values.
- Identity grants and deterministic verification authorize.
- LangGraph coordinates checkpoints and interrupts; it does not make policy.
- Registered operators are the only executable primitives.
- External context is untrusted evidence until tested.
- Verification binds an immutable plan digest.
- High-risk actions require explicit grants and approvals.
- Failures and denials are evidence and must be recorded.

Do not add a second workflow, capability, component, task, or dynamic-code execution
abstraction. Do not let a model create operators, permissions, approvals, policy, or
ledger entries directly.

Prefer strict Pydantic contracts, small services, append-only records, deterministic
tests, and provider-neutral adapters. Core tests must run with a fake planner and
without a network, model provider, Graphiti server, or remote host.
