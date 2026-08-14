# Initial-Import Decision Gate

## Decision status

- Decision: `allow_with_warning`
- Allowed: `true`, scoped to initial import only
- Approval record: `40_output/approvals/APP-MERCURY-INITIAL-IMPORT-0001.yaml`
- Proposal: `PROP-MERCURY-INITIAL-IMPORT-0001`
- Risk: `high`

## What happened

An independent governance review initially deferred the action. The project owner subsequently gave explicit approval for the exact initial import proposed. The approval is scoped to creating one immutable version from the seven hashes in `10_context/local-intake.md`.

## What remains blocked

Experiment planning/execution, prediction generation, and submission remain blocked. The immediately authorized next actions are initial-import version creation, then read-only time-aware leakage audit and characterization.

## Satisfied condition

The project owner explicitly approved creation of the immutable initial-import dataset version from the seven SHA-256-hashed, read-only official files documented in `10_context/local-intake.md`.

## Checks

- Local-only privacy: `pass`
- Remote execution: `blocked`
- External providers: `blocked`
- External data: `blocked`
- Post-intake network: `blocked`, except separately decided submission
- Budget: no fixed cap; per-task usage tracking required
- Tool/comparability: `not_available` until a dataset version and temporal evaluation policy exist

## Provenance

- Review date: 2026-08-13
- Source artifacts: `10_context/local-intake.md`; `10_context/current_state.md`; `30_evidence/task-ledger.md`; `40_output/initial-import-proposal.md`; `00_task/constraints.md`
- Policy references: `_architecture/08_DECISION_SYSTEM.md`; `_architecture/14_GOVERNANCE.md`

## Artifact contract

- **READ:** initial-import proposal and supporting intake evidence.
- **DO:** evaluate authorization only; do not create the dataset version or execute characterization.
- **WRITE:** this decision-gate handoff and a future durable decision/approval record.
