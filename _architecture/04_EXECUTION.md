# Verification and execution

The verifier rejects unknown operators, invalid dependencies, stale or missing
identity grants, unsupported risk, missing evidence references, and absent approvals.
A decision binds the plan digest and policy version.

The executor is intentionally unintelligent. It executes the verified order, validates
operator inputs and outputs, uses deterministic idempotency keys, blocks dependents
after failure, and records structured results. It cannot repair or reinterpret a plan.

Operators replace the former tool, capability, and component abstractions.

Authorization is recalculated immediately before execution. Revoked or expired grants
and approvals therefore invalidate an earlier decision. Equivalent allowed decisions
are content-deduplicated; changed authority state creates a different decision.

Each operator runs in its own process group and private 0700 workspace with time,
memory, file-size, output-size, and environment limits. Cancellation and timeout
terminate the process group. Only regular files inside the workspace can be promoted
to the content-addressed artifact store; symlinks and escaping paths are rejected.

Idempotent successes may be reused by a key over the plan, step, operator version, and
implementation digest. A non-idempotent process that exits without a durable result is
never retried automatically; its run enters `reconciliation_required`.
