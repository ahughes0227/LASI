---
description: Review diagnostic artifacts and produce a provider-neutral scientist review.
agent: scientist-reviewer
---

Use the scientist-review skill for `$ARGUMENTS`. Use the provider normalization and diagnostic-packet services to produce observations, confidence, ranked recommendations, artifact references, and provenance. Recommendations must remain separate from authorization and execution; do not call tools or bypass `lasi.decisions.gate.DecisionGate`.
