# Architecture

## Constitutional loop

There is one runtime graph:

1. Retrieve a bounded memory snapshot.
2. Derive deterministic exploration directives.
3. Ask a provider-neutral LLM planner for a typed declarative plan.
4. Verify the plan against identity, policy, operators, evidence, and approvals.
5. Interrupt for approval or stop on denial.
6. Execute registered operators in dependency order.
7. Append every result and failure to the ledger.
8. Project ledger events into semantic memory.

LangGraph implements this state machine. Static workflows are not a subsystem.
Reusable approaches may be planner examples, but they confer no execution authority.

## Sources of truth

| Concern | Authority |
| --- | --- |
| events, plans, decisions, runs | append-only SQL ledger |
| execution permission | identity grants and deterministic verifier |
| operator behavior | versioned operator registry |
| produced binaries | artifact store |
| semantic retrieval | rebuildable Graphiti projection |
| orchestration progress | LangGraph checkpoint |

Contracts have no service dependencies. The LangGraph adapter composes services but
contains no business authority.
