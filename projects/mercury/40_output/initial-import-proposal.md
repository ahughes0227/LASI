# Initial-Import Dataset Version Proposal

## Proposal

- Proposal ID: `PROP-MERCURY-INITIAL-IMPORT-0001`
- Status: `submitted_for_approval`
- Risk: `high`
- Requested action: create the initial immutable dataset version from the seven read-only, hashed official challenge inputs.

## Scope

The proposed version would preserve source paths and hashes from `10_context/local-intake.md`, use change type `initial_import`, and set comparability to `unknown` until the evaluation policy and temporal split are confirmed. It would not alter labels, source records, split definitions, benchmark definition, privacy policy, or source storage.

## Evidence

- `10_context/local-intake.md`
- `30_evidence/task-ledger.md`
- `40_output/kaggle-cli-authorization.md`

## Approval required

Explicit approval is required before dataset-version creation. After approval, the next action is a read-only time-aware leakage audit and characterization. This proposal is not an approval and does not authorize training or a submission.

## Artifact contract

- **READ:** local intake record, file hashes, and approval decision.
- **DO:** create a lineage-preserving initial-import version only after approval.
- **WRITE:** dataset-version and manifest records, characterization handoff, and operational-memory records.
