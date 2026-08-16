---
description: Build a governed LASI component package from a structured request.
agent: lasi-component-builder
---

Develop the component described by `$ARGUMENTS` using the canonical
`component-development` skill and `services.components` contracts/services.
Discover candidates through the PlannerCatalog, validate them against the
authoritative ComponentRegistry, and perform mandatory REUSE, COMPOSE, EXTEND,
or NEW resolution before research or implementation.

Freeze a `ComponentBuildPlan`, build only inside the fixed component package
shell, validate contracts, tests, evaluations, runtime metadata, granularity,
and provenance, then create a `ComponentRegistrationProposal`. Stop for the
explicit `update_toolbox` approval; do not register or execute generated code
merely because the package was written.
