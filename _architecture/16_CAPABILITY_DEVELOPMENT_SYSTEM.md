# Capability Development System

## Purpose

This document defines how LASI expands its own action space through repeatable,
governed capability development. It owns capability intent, semantic discovery,
deduplication, gap analysis, bounded research, build planning, fixed-shell
packages, validation, impact analysis, and registration proposals.

It does not replace the component registry, tool registry, OpenCode skills,
decision system, ICM, operational memory, or governance. A capability describes
what LASI can do. A component describes reusable implementation machinery. A
tool remains an approved executable boundary.

The system answers:

> Does this capability already exist, can it be extended or composed, what is
> genuinely missing, and what evidence is required before LASI may trust it?

## Core Principle

Capability development is a governed compiler pipeline, not a free-form coding
agent:

```text
intent
→ CapabilitySpec
→ REUSE | COMPOSE | EXTEND | NEW
→ exact gap
→ minimum-sufficient context
→ source-backed research decisions
→ frozen CapabilityBuildPlan
→ fixed capability shell
→ contract/test/evaluation validation
→ registration proposal
→ explicit approval and registration
```

Natural language is interpreted once into a typed intermediate representation.
Downstream stages operate on the contract and durable stage artifacts instead
of repeatedly reinterpreting the original prompt.

## Operating Surface

`/lasi-build-capability <description>` is the OpenCode entry point. It uses the
`lasi-capability-builder` agent and canonical `capability-development` skill.
The command may create and revise a draft package. It does not itself authorize
shared registration or execution of generated code.

This is a distinct governed development operation, not a replacement for
`/lasi-start`. Normal ML research assignments remain under the durable task
runtime and its decision gates.

## Canonical Contracts

`CapabilitySpec` is the semantic intermediate representation. It declares
identity and version, purpose, accepted and produced artifact types, operations,
guarantees, constraints, side effects, explicit exclusions (`does_not`),
capability/component dependencies, execution kind, lifecycle, and provenance.

Other stage contracts are:

```text
CapabilityCandidate             structural candidate comparison
CapabilityResolution            mandatory dedup decision
CapabilityResearchDecision      source-backed answer to one gap
CapabilityBuildPlan             frozen implementation authority
CapabilityValidation            deterministic validation evidence
CapabilityRegistrationProposal  governed request to expand the runtime
```

## Registry and Catalog Boundaries

The capability registry indexes semantic manifests and answers what LASI can
do. The component registry remains the explicit catalog of executable,
schema-backed implementation primitives. The tool registry remains the
execution allowlist checked by the decision system.

`system/capabilities/` contains ICM descriptions used for bounded context and
semantic discovery. Fixed-shell packages under `capabilities/` contain typed
manifests, contracts, implementation declarations, tests, evaluations, and
provenance. Neither location dynamically imports implementation code.

Executable binding remains explicit in the component or tool registry. A
registered semantic capability is not automatically an executable component.

## Mandatory Resolution

A package may not be built or registered until the resolver produces exactly
one action:

```text
REUSE    one existing capability satisfies the contract
COMPOSE  compatible existing capabilities cover it together
EXTEND   one owning abstraction lacks a bounded set of requirements
NEW      LASI genuinely lacks the primitive
```

Resolution compares purpose, inputs, outputs, operations, guarantees,
constraints, and explicit exclusions separately. Retrieval or embeddings may
find candidates later, but similarity alone never establishes a duplicate.
`does_not` prevents a superficially similar capability from being treated as a
match when it explicitly excludes a required operation.

REUSE must not create a package. COMPOSE is preferred to new implementation.
EXTEND requires dependent-impact and compatibility review. NEW researches and
implements only the missing primitive.

## Context and Research

The builder receives minimum-sufficient context: the request and resolution,
selected manifests and component schemas, runtime contracts and architecture
boundaries, allowed dependencies and side effects, dependents, and evaluation
and governance requirements. It may expand context only to answer a recorded
gap.

Research output is a `CapabilityResearchDecision`, not an unbounded essay. Each
decision records the question, alternatives, selection, rationale, rejected
approaches, confidence, sources, and provenance.

## Build Plan and Fixed Shell

The `CapabilityBuildPlan` freezes resolution, reused building blocks, research
questions, files, tests, evaluations, registration scope, and provenance before
implementation. A material scope or architecture change requires a plan
revision rather than silent drift.

Every non-REUSE build uses this shell:

```text
capabilities/<capability_id>/
├── capability.yaml
├── contract/{input.schema.json,output.schema.json}
├── implementation/{pipeline.yaml,custom/}
├── tests/{contract,functional,integration,regression,fixtures}/
├── evaluation/eval.yaml
├── provenance/
│   ├── resolution.yaml
│   ├── build-plan.yaml
│   ├── research-decisions.yaml
│   ├── validation.yaml
│   └── registration-proposal.yaml
└── README.md
```

Boilerplate is generated mechanically by
`CapabilityDevelopmentService.scaffold`. The model uses its effort on research,
composition, implementation, tests, and evaluation evidence.

## Validation

`CapabilityPackageValidator` fails closed. Registration cannot be proposed
unless the fixed shell is complete, typed manifests and build plans validate,
dedup provenance is attached, JSON contracts are valid, executable tests exist,
evaluation cases exist, research gaps are resolved, and the dependency graph is
valid.

The command also runs repository-appropriate tests, formatting, lint, type
checks, dependency review, and security/containment review. The package hash
binds those results to the exact files proposed for registration.

## Registration and Authority

`CapabilityRegistrar.propose` writes a registration proposal only after
validation passes. Shared registration is a toolbox change and requires a
matching approved `ApprovalRecord` whose action is `update_toolbox`.

The registrar rechecks the package hash before registration. Changed content
invalidates the prior validation and approval. Generated or third-party code
that will execute must also pass the existing component-review, static-binding,
resource, dependency, side-effect, and containment gates. Project-local
experimental authorization never implies shared registration.

Registration records what was approved; it does not allow proposal data to
carry an import path or cause code execution.

## Provenance and Versioning

Every build preserves the request, resolution, research decisions, plan,
validation, proposal, approval, package hash, dependencies, tests, evaluations,
and affected capability IDs. Extensions must inspect dependents and choose a
compatible minor version or a breaking major version deliberately.

Failed builds, rejected duplicates, incomplete validation, and denied
registrations remain evidence. They must not be deleted merely because no
capability was registered.

## Initial Scope

The initial implementation provides typed contracts, structural resolution,
semantic manifest discovery, component discovery, deterministic scaffolding,
structural validation, package hashing, registration proposals, approval-bound
registration, and the OpenCode command/agent/skill. The planner catalog now
projects registered capabilities, components, workflows, and workflow nodes
into a traversable SQLite graph. Candidate discovery may be lexical today and
may add a vector index later; graph traversal and contract validation remain
authoritative for planner composition.

Component development is the separate governed path for creating reusable
implementation primitives. It uses the planner catalog for candidate discovery
and impact analysis, but uses `ComponentRegistry` for authoritative contract
comparison and execution binding. Component relationships remain single-sourced
by `CapabilitySpec.component_dependencies`.

Learned semantic retrieval, automatic impact scoring, package signing, remote
build isolation, and autonomous shared promotion require separate evidence and
design. Automatic shared registration is intentionally out of scope.

## Workflow Builder Relationship

Workflow development mirrors this capability lifecycle because workflow graphs
expand LASI's governed control surface. The workflow builder uses the same
SPECIFY → RESOLVE → GAP → CONTEXT → RESEARCH → PLAN → BUILD → VALIDATE → PROPOSE
stages, but its canonical intermediate representation is `WorkflowDefinition`,
its fixed shell is a JSON workflow package, and its registration proposal is
`WorkflowRegistrationProposal`.

Workflow development remains distinct from capability development: a capability
describes what LASI can do, while a workflow describes how approved work may be
routed. The workflow builder may bind capabilities and skills, but it cannot
create executable authority or bypass SQLite decisions.
