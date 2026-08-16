---
description: Build a governed LASI capability from a natural-language request.
agent: lasi-capability-builder
---

Develop the capability described by `$ARGUMENTS` using the canonical
`capability-development` skill and `services.capabilities` contracts/services.
Perform mandatory structural deduplication before research. Freeze a
`CapabilityBuildPlan`, research only unresolved gaps, implement only inside the
fixed capability shell, and validate contracts, tests, evaluation cases,
dependencies, provenance, and side effects. Prefer REUSE, then COMPOSE, then
EXTEND, before NEW. A REUSE result must not create a duplicate package.

The command authorizes creation and revision of a draft package. It does not
authorize shared-toolbox registration. If validation passes, create a
`CapabilityRegistrationProposal` and stop for explicit `update_toolbox`
approval. Report the resolution, package path, validation status, and proposal
ID. Do not register or execute generated code merely because it was written.
