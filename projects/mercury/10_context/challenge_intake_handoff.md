# Challenge Intake Handoff

## Status

`superseded_by_local_intake`

## Public metadata (unverified locally)

- Challenge title: Store Sales - Time Series Forecasting
- Public URL: <https://www.kaggle.com/competitions/store-sales-time-series-forecasting>
- Reported metric: RMSLE
- Reported submission columns: `id`, `sales`

These statements are preliminary public metadata, not an executable `ChallengeSpec`.

## What happened

At the time this handoff was created, no local challenge files were inspected. It is historical intake evidence and is superseded by `10_context/local-intake.md`; consult that artifact for the current inventory and state.

## Required local inputs

Provide a local challenge-scoped folder containing training, test, and sample-submission files, plus any locally available rules or data dictionary. Intake must record each supplied file's relative path, role, byte size, SHA-256, parser/format-adapter outcome, and rejection reason when applicable.

## Consequential unknowns

| Field | Status |
|---|---|
| Target, ID, time, group, and prediction columns | `unknown_requires_local_confirmation` |
| Metric behavior and edge cases | `not_locally_verified` |
| Forecast horizon and split semantics | `unknown_requires_local_confirmation` |
| Submission schema and row count | `not_available` |
| Challenge rules, status, deadline, and limits | `not_locally_verified` |
| Privacy classification | `not_assessed` |

## Required next handoff

Dataset intake may proceed only with supplied local files under benchmark isolation: no network, external providers, remote execution, arbitrary subprocesses, external data, or hidden-label access. Perform leakage audit before characterization. Findings must not mutate source data, labels, splits, or benchmark definitions.

## Artifact contract

- **READ:** locally supplied challenge files and locally supplied rules/schema.
- **DO:** inventory, safe format inspection, SHA-256 hashing, schema confirmation, and leakage audit.
- **WRITE:** immutable intake inventory, hashes, typed `ChallengeSpec`, leakage-audit result, and workspace references.
