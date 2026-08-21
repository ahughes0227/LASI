# Verification and execution

The verifier rejects unknown operators, invalid dependencies, stale or missing
identity grants, unsupported risk, missing evidence references, and absent approvals.
A decision binds the plan digest and policy version.

The executor is intentionally unintelligent. It executes the verified order, validates
operator inputs and outputs, uses deterministic idempotency keys, blocks dependents
after failure, and records structured results. It cannot repair or reinterpret a plan.

Operators replace the former tool, capability, and component abstractions.
