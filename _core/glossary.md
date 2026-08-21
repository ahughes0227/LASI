# Glossary

**Belief**: a confidence-bearing semantic claim with evidence and validity time.

**Evidence**: an observation with provenance and an explicit trust level.

**Exploration directive**: deterministic pressure to leave a stagnant search area.

**Identity snapshot**: immutable grants and roles used to verify a plan.

**Approval request**: authority record bound to one immutable plan step and risk tier.

**Ledger**: append-only authoritative operational record.

**Operator**: the only executable primitive; a versioned contract plus registered code.

**Plan**: immutable declarative operator graph proposed by a planner.

**Planner**: provider-neutral LLM adapter that recommends and has no authority.

**Projection**: rebuildable semantic index, normally Graphiti.

**Reconciliation required**: terminal automated-execution state for an ambiguous,
non-idempotent operation whose effects must be inspected before any retry.

**Signed action**: payload-bound Ed25519 authorization with expiry and replay-protected
nonce.

**Verifier**: deterministic policy kernel that authorizes or denies an exact plan.
