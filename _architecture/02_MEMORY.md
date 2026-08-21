# Memory

The SQL ledger records what happened. Graphiti makes that history retrievable as a
temporal belief graph. Projection failures cannot erase or alter ledger records.

Every belief has confidence, evidence references, validity time, and optional
invalidation time. Extracted Graphiti edges are hypotheses by default. Promotion to an
authoritative fact or policy is a governed operator action.

External context enters as untrusted Evidence. It may create exploration pressure and
inform hypotheses, but never expands an identity grant or bypasses an approval.

The authoritative context path always reads evidence and run summaries from SQL.
Graphiti contributes bounded beliefs when available. If retrieval fails, context carries
an explicit degraded projection status and warning while authoritative work continues.

Every authority event is placed in a transactional outbox with a stable event UUID.
The projection worker retries with bounded exponential delay and dead-letters after ten
failed deliveries. Replaying an event is safe because Graphiti receives that stable UUID.
Graphiti is expected to use a Neo4j Community backend in the supported deployment.
