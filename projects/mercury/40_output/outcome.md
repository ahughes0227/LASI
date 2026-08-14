# Project Outcome

## Current status

- Project outcome: `cancelled`
- Reason category: `approval_block`
- Owner decision: the project owner responded to pending escalation
  `mercury-isolated-host-profile-001` with “end the project and report.”
- Decision date: 2026-08-13
- Recorded by: LASI coordinator at 2026-08-13T21:40:52Z

## Disposition

The owner intentionally ended Mercury after no actionable approved isolated host
profile or challenge-data-transfer boundary existed. This is a cancellation, not
`failed_validation`.

## Validation, deployment, and production

| Area | Status | Evidence boundary |
|---|---|---|
| Validation | `partial` | Direct GBDT is the best comparable local result: RMSLE `0.4609337296`. |
| External benchmark | `recorded` | Kaggle public score `0.49942`, submission `55489163`. |
| Deployment | `not_deployed` | No deployment was authorized or recorded. |
| Production | `not_in_production` | No production evidence exists. |

The public score is external benchmark evidence only; it is not a private score
or a production outcome.

## Blocked containment path

The hurdle component never performed challenge execution. Containment work did
not perform remote validation, data staging, a valid attempt, or quota
consumption. No benchmark data was modified.

## Append-only outcome event and provenance

- Event: `30_evidence/outcomes/mercury-outcome-event-001.json`
- Direct GBDT outcome: `40_output/direct-gbdt-outcome.md`
- Submission record: `30_evidence/mercury-direct-gbdt-submission-001-submission-record.json`
- Backend configuration assessment: `30_evidence/mercury-protected-backend-configuration-assessment-001.json`
- Hurdle result state: `20_work/experiments/mercury-hurdle-panel-forecast-001/results.md`

No report was generated for this closure.
