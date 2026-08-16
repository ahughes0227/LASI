---
description: Build a governed LASI workflow package from a structured request.
agent: lasi-workflow-builder
---

Develop the workflow described by `$ARGUMENTS` using the canonical
`workflow-development` skill and `services.workflows` contracts/services.
Perform mandatory structural deduplication before research. Freeze a
`WorkflowBuildPlan`, research only unresolved gaps, build only inside the fixed
workflow package shell, and validate graph correctness, bindings, tests,
evaluation cases, authority boundaries, and provenance.

Prefer REUSE, then COMPOSE, then EXTEND, before NEW. A REUSE result must not
create a duplicate package. If validation passes, create a
`WorkflowRegistrationProposal` and stop for governed review. Do not install,
execute, or treat generated workflow JSON as authorization merely because it
was written.
