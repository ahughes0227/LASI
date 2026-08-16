# Component Development System

## Purpose

The component development system creates reusable, registered implementation
primitives that the planner may compose into executable plans. A component is
trusted, versioned code with one stable responsibility, typed artifact ports,
and validated configuration.

Components may be implemented in Python, TypeScript, Rust, or Go. The runtime
plan selects a component ID, version, configuration, and artifact references.
It never supplies source code, import paths, commands, control flow, or
executable expressions.

## Authority and Discovery

Component packages and `ComponentRegistry` are authoritative for component
metadata and executable bindings. `PlannerCatalog` is a rebuildable SQLite
projection of approved registry metadata. It supports lexical discovery and
typed graph traversal, but it does not authorize execution and is not an
epistemic knowledge graph.

Candidate retrieval is not compatibility proof. The resolver retrieves
component nodes from `PlannerCatalog`, then loads authoritative
`ComponentSpec` metadata from `ComponentRegistry` and compares responsibility,
configuration boundary, ports, exclusions, and operational requirements.

Graph relationships do not grant execution authority. The tool registry and
decision system remain responsible for allowing a component pipeline to run.

## Component Granularity

A component owns one stable responsibility. Configuration tunes that
responsibility; it does not select unrelated operations. `rename_file` is a
valid generic component. `rename_finance_pdfs` is a domain-specific duplicate.
`manage_file(operation=rename|copy|delete)` is too broad because configuration
selects unrelated operations.

The resolver uses:

```text
REUSE    one registered component satisfies the contract
COMPOSE  existing components can form the requested graph
EXTEND   one component owns the responsibility but needs bounded expansion
NEW      no registered component or composition satisfies the request
```

COMPOSE normally produces a graph recommendation rather than a wrapper
component. A reusable macro with its own stable responsibility belongs in a
capability or workflow package.

## Development Lifecycle

```text
intent
→ PlannerCatalog discovery
→ authoritative ComponentRegistry comparison
→ resolution
→ impact analysis
→ bounded research
→ frozen ComponentBuildPlan
→ fixed component package
→ contract/test/evaluation validation
→ ComponentRegistrationProposal
→ explicit update_toolbox approval
→ ComponentRegistry registration
→ PlannerCatalog reprojection
```

Project-local experimental component generation remains a separate path. This
workflow creates shared registered components and does not weaken or replace
the existing `ComponentRequest` and `ComponentReview` contracts.

## Fixed Package

```text
components/<component_id>/
├── component.yaml
├── contract/{config.schema.json,input.schema.json,output.schema.json}
├── implementation/{runtime.yaml,src/}
├── tests/{contract,functional,integration,regression,fixtures}/
├── evaluation/eval.yaml
├── provenance/
└── README.md
```

The package records source, dependency-lock, toolchain, and optional compiled
artifact evidence. A package is not trusted or executable merely because it
exists or its tests pass.

## Runtime Bindings

Approved Python components execute through their trusted handler binding.
TypeScript, Rust, and Go components use a lightweight subprocess adapter with
configuration and artifact references as inputs and structured result JSON,
logs, and exit status as outputs. Missing language toolchains are recorded as
`not_available`; LASI does not install them automatically.

Isolation is intentionally limited to high-return execution hygiene: component
work directories, explicit artifact paths, output validation, log capture, and
optional timeouts. Components are prescreened trusted code, not adversarial
agent-generated code requiring a hardened sandbox.

## Registration and Projection

Registration requires a matching approved `update_toolbox` record and a package
hash. Registration records the component and then asks `PlannerCatalogBuilder`
to rebuild the derived planner projection from authoritative registries. The
registrar never inserts planner rows individually.

If projection fails, registration evidence is preserved with an explicit stale
projection status. A later complete rebuild repairs discovery without silently
changing the component registration.

Capability relationships remain single-sourced by
`CapabilitySpec.component_dependencies`. A component is discoverable without
being declared an implementation of a capability. Adding that relationship is
a separate governed capability change.
