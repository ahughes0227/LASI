# Kaggle CLI Authorization Review

## Decision scope

| Action | Outcome | Risk | Allowed |
|---|---|---:|---:|
| Download official Store Sales challenge assets with Kaggle CLI for local intake | `allow_with_warning` | medium | `true`, one acquisition attempt |
| Submit a prediction with Kaggle CLI | `request_clarification` | high | `false`, separate decision per artifact |

## Scope and conditions

The user authorized Kaggle CLI download and submission through their account/team, web research, local-only compute, and no external providers. This authorizes only retrieval of official challenge assets into a challenge-scoped local intake folder. It does not authorize external data, remote compute, external scientist providers, benchmark modification, dataset mutation, training, prediction, or submission.

Record CLI version, retrieval time, command outcome, file paths, sizes, hashes, and task result. Preserve source files unchanged. After acquisition, benchmark isolation resumes: network, external providers, remote execution, arbitrary subprocesses, external data, and hidden-label access are denied.

## Submission gate

Every submission remains unapproved until a decision identifies the user-authorized account/team, current submission limit, a validated prediction artifact checksum, local `ChallengeSpec`, experiment and decision references, and its intended submission purpose. Record the Kaggle response and submission identifier as external evaluation evidence.

## Policy and provenance

- Prepared by: LASI coordinator
- Prepared at: 2026-08-13
- User authorization: 2026-08-13
- Policy references: `_architecture/08_DECISION_SYSTEM.md`; `_architecture/14_GOVERNANCE.md`; `00_task/constraints.md`
- Source artifacts: `10_context/challenge_intake_handoff.md`; `10_context/current_state.md`; `40_output/authorization-status.md`

## Artifact contract

- **READ:** this scoped authorization, challenge identifier, and Kaggle CLI authentication state.
- **DO:** retrieve official challenge files once for governed local intake; record success or structured failure.
- **WRITE:** acquisition result, immutable intake inventory and hashes, and task/usage ledger entries.
