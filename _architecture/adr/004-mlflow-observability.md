# ADR-004: MLflow as the trace and experiment spine

**Status:** accepted

## Context

MLflow is already a declared dependency and is named throughout `_architecture/`
as the experiment record. In practice it is barely wired: a single
`mlflow_run_id` field on `ToolRunResult`, and `MlflowArtifactStore` used by a
narrow set of paths. Meanwhile ADR-002 introduces plan rankers that must be
compared against each other, which needs somewhere to record the comparison.

## Decision

Use MLflow as the trace, metric, and experiment-comparison spine. The relational
store remains **authoritative for operational state**; MLflow is a record of what
happened, never a source of truth the runtime reads back to make decisions.

Record, where applicable: workflow and version, capability and version,
component and version, model, prompt/program version, ranker version, template
revision (ADR-008), admissible-set size, chosen plan, input and output
references, duration, token counts, cost, evaluation score, critic result, human
feedback, errors, and artifacts.

### Token accounting keeps LASI's stricter rule

External guidance said "cost where available". LASI's existing rule is stricter
and is retained: exact token counts and billed cost are recorded **only** when
the provider or agent runtime returns an authoritative receipt. Usage is never
derived from prompt text, estimated by a model, or computed from a price table.
Non-token actions are `not_applicable`; missing receipts are `not_available`.

### MLflow needs a database backend

MLflow's filesystem store (`./mlruns`) is in maintenance mode and raises on
initialisation unless explicitly opted into. A database backend is therefore required:
SQLite locally, and the same PostgreSQL the operational store uses once ADR-003 lands.

This is consistent with the single-datastore principle rather than an exception to it.
MLflow manages its own tables; it does not share LASI's. Nothing about operational state
moves into MLflow, and MLflow is not read back.

### The metering rule is enforced by the contract, not by the adapter

`ProviderTokenUsage` refuses a `reporting_source` containing "estimate", and
`ActionTokenUsage` requires an explicit reason whenever status is `not_available`. The
tracer therefore cannot log an invented number even incorrectly: the object carrying one
cannot be constructed. The adapter logs token metrics only for `reported` usage and
records the status and reason otherwise.

This matters more than it looks. An estimate logged beside real receipts is
indistinguishable from one, and every later cost total would silently include fiction.

## Consequences

- The questions "why did LASI choose this path" and "did this path perform
  better than the alternatives" become answerable from records rather than from
  agent transcripts.
- Answering the second question properly requires the retained counterfactuals
  from ADR-002. MLflow stores the comparison; the planner has to produce it.
- Two stores hold overlapping information. The boundary must stay explicit:
  operational state and governance in the relational store, observation and
  comparison in MLflow. Any code path that reads MLflow to decide what to do next
  is a defect.
