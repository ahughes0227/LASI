# Governance

The identity snapshot answers who may request which operator, at what risk, in which
project, until when. The policy verifier answers whether this exact plan may proceed.
Approval requests are authority records bound to the immutable plan and step digest;
the planner cannot supply or select approvals.

High-consequence actions remain high or critical risk, including dataset mutation,
benchmark changes, external raw-data transfer, knowledge promotion, deployment,
operator registration, and remote trust changes.

The model cannot edit identity, risk ratings, policy, approvals, ledger history, or
the operator registry.

Local identities use Ed25519 credentials. Start, resume, cancel, inspect, and approval
actions are payload-bound, short-lived signatures with persistent nonce replay
protection. High-risk or explicitly governed steps require one approver distinct from
the requester. Critical steps require two distinct approvers. A denial is terminal for
that plan revision, and grant revocation or expiry is checked again before execution.

The reference deployment uses private local directories and 0600 state files. This is
access control, not payload encryption; hosts that require encrypted local data must add
an encrypted volume or database layer below these services.
