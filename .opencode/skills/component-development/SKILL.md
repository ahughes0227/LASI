---
name: component-development
description: Use when discovering, resolving, researching, building, validating, or proposing registration of a LASI component.
---

# Component Development

Use this lifecycle exactly:

```text
SPECIFY → DISCOVER → RESOLVE → IMPACT → GAP → RESEARCH → PLAN → BUILD → VALIDATE → PROPOSE
```

Compile intent into `ComponentSpec`. Use `PlannerCatalog.find_components_for_need`
for candidate discovery, then load authoritative `ComponentSpec` values from
`ComponentRegistry`. Retrieval alone never establishes REUSE.

Apply exactly one resolution:

1. `reuse` when one registered component satisfies the stable responsibility;
2. `compose` when existing components can form the requested graph;
3. `extend` when one component owns the responsibility but needs bounded change;
4. `new` only when no registered component or composition satisfies it.

Configuration may tune one responsibility. It must not select unrelated
operations. Prefer generic components such as `rename_file` over domain-named
duplicates.

Freeze `ComponentBuildPlan` before implementation. Build only through
`ComponentDevelopmentService.scaffold` and preserve its fixed package shell.
Validate with `ComponentPackageValidator`; require contracts, executable tests,
evaluation cases, runtime metadata, granularity evidence, and provenance.

Use direct trusted Python bindings by default. Use the lightweight subprocess
adapter for TypeScript, Rust, and Go. Missing toolchains are `not_available`;
do not install them automatically.

Use `ComponentRegistrar.propose` only after validation passes. Shared
registration requires a matching approved `update_toolbox` record and triggers
complete PlannerCatalog reprojection. A proposal is not registration or
execution authority.
