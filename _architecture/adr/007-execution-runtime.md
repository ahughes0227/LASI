# ADR-007: Execution runtime — no LangGraph, no Temporal

**Status:** accepted

## Context

`TaskRuntimeService` is a hand-written durable execution engine: leases with
expiry recovery, immutable attempts, dependency-gated readiness, event logs,
context snapshots, retries, and resume. Writing durable execution in-house
normally deserves scrutiny — it is generic infrastructure, and the standing
engineering preference is to use maintained tools rather than debug our own.

Two candidates were evaluated to replace or supplement it.

## Decision

**Neither is adopted.** The reasoning differs for each, and both are recorded
here so the question does not recur on every architecture reread.

### LangGraph — declined, duplicates what exists

Feature by feature, its offer is already met:

| LangGraph provides | LASI equivalent |
|---|---|
| Graph / state-machine definition | `_workflows/*/workflow.json` + `WorkflowCompiler` + `TaskSpec` dependencies |
| Typed graph state | `AgentTask` / `AgentResult` / `DomainStateSnapshot`, all `StrictModel` |
| Checkpoint persistence | `runtime_tasks`, `task_attempts`, `context_snapshots`, `task_events` |
| Resume after crash | `_recover_expired_leases` + `admin.resume()` |
| Retries | `max_attempts` + `task_retry_ready` |
| Conditional branching | `WorkflowActivation`, `WorkflowSkipPolicy`, extension policy |
| Subgraphs | Workflow COMPOSE/EXTEND; `ComponentGraphRunner` nested in a task |
| Human interrupts | Decision gates, `human_review_required`, escalation, pause |
| Parallel fan-out | Multiple lease owners over ready tasks |
| Token streaming | Not needed — batch research, not chat |

It also has no concept of three properties the runtime enforces: decision-gate
enforcement, token receipts with `not_available` semantics and reconstructed
autonomy budgets, and plateau detection with automatic critic tasks. Adopting it
means wrapping it for no benefit, or reimplementing those on someone else's
execution model. It would additionally be a *third* execution mechanism beside
`TaskRuntimeService` and `ComponentGraphRunner`.

### Temporal — evaluated seriously, declined on fit

Temporal is the stronger candidate and is unambiguously better engineered than
anything written here: real durable execution, retry policies, four timeout
kinds, heartbeats, signals, child workflows, versioning, a visibility UI, years
of production hardening.

The deciding question is not quality but whether adopting it lets us **delete**
`TaskRuntimeService`. If it does, adopt. If it does not, we run a server and keep
the code anyway. It does not, and the reason is in the schema:

```
runtime_tasks.decision_id        → FOREIGN KEY decisions.decision_id
runtime_tasks.experiment_plan_id → FOREIGN KEY experiment_plans.experiment_plan_id
runtime_tasks.rubric_key         → FOREIGN KEY reasoning_rubrics.rubric_key
```

`runtime_tasks` is not an execution-engine table that happens to live in the
operational database. It is **part of the governance schema**, with referential
integrity to decisions and plans, mutated inside caller-owned transactions
(`ingest_proposal_in_transaction`, "so the graph advances atomically"). The rule
"a task cannot reference a decision that does not exist" is enforced by the
database, not by application code that some path might skip.

Move execution state into Temporal's store and that constraint cannot exist:
two sources of truth, no transaction spanning them, and the decision gate demoted
from a database invariant to application logic that must be correct on every
path. In practice the tables and the state machine would be kept and Temporal
used only for retry and timeout — while adding a server, a second datastore, and
workflow-determinism constraints on code that currently calls an LLM and a
planner freely.

A second, softer mismatch: LASI's graph is proposed at runtime by an agent
(`TaskGraphProposal`) and stored as data, then pulled by leasing workers.
Temporal's model is a workflow function awaiting activities. Expressing a
dynamic, LM-authored, data-resident DAG in it reduces to a workflow that loops
"read next ready task → run activity → write result" — which is
`TaskExecutor.run_once` with a server in front of it.

## Revisit conditions

Reopen this decision if any becomes true:

- Workers distributed across machines needing heartbeat-based failover.
- Processes running for days with genuine compensation logic.
- Execution state no longer needing to join against governance state.

None hold today.

## Consequences

Keeping the runtime means owning its defects. Three were found while evaluating
the alternatives, and closing them is the work this decision implies:

1. **Retry has no backoff.** A failed task is set straight back to `ready`, so a
   deterministically-failing task burns every attempt in a hot loop. Needs a
   persisted `next_eligible_at` honored by `lease_ready_task` — persisted rather
   than in-process, because the wait must survive a crash.
2. **`lease_ready_task` has no row locking.** `with_for_update` appears nowhere
   in the codebase. SQLite hides this by serializing writes; ADR-003's Postgres
   migration activates it as a real double-lease race. The fix is SQLAlchemy's
   `.with_for_update(skip_locked=True)` — the maintained Postgres primitive that
   sits underneath every Postgres-backed job queue, including Temporal's own
   persistence layer. This is the preference for maintained tooling applied
   correctly, rather than resisted.
3. **Concurrency is untested.** Every existing test leases as `"runtime-1"`.
   Fan-out is architecturally supported and entirely unproven.

Note that none of the three would have been fixed *for us* by adopting either
candidate; #2 in particular is a bug in how we query Postgres, not in what
executes the graph.

### Resolution

All three are closed. Locking landed with the PostgreSQL migration (ADR-003), since that
move is what makes the race reachable; backoff and the concurrency tests followed.

Backoff is exponential from 30 seconds, capped at 10 minutes. The cap is deliberate: the
point is to leave an interval in which the cause could change, not to wait a problem out.
Past a few minutes a task is waiting for a human, not for a transient.

Two details worth recording:

* **Expired-lease recovery deliberately does not back off.** That path is already spaced
  by the lease duration, so adding a second delay would compound them.
* **`lease_ready_task` gained an optional `now`.** Backoff is otherwise only testable by
  sleeping, and a suite that sleeps for its own retry schedule is one nobody runs. The
  parameter is for tests; production callers leave it unset.

Adding backoff changed real behaviour that an existing test depended on: a token-ceiling
test leased immediately after a failure and had assumed that was possible. It now leases
past the delay explicitly. The assumption was correct before this change and is not
correct after it, which is the kind of thing a test is supposed to catch.
