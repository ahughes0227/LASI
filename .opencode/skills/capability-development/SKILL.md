---
name: capability-development
description: Use when resolving, researching, building, validating, or proposing registration of a LASI capability.
---

# Capability Development

Use this lifecycle exactly:

```text
SPECIFY → RESOLVE → GAP → CONTEXT → RESEARCH → PLAN → BUILD → VALIDATE → PROPOSE
```

Registration is a separate governed transition after `PROPOSE`.

## Specify

Compile the user's intent once into `CapabilitySpec`. Make purpose, accepted and
produced artifact types, operations, guarantees, constraints, side effects,
explicit exclusions, and execution kind concrete. Do not carry action-driving
requirements only in prose.

## Resolve before research

Build a `CapabilityRegistry` from fixed-shell manifests and add the descriptions
under `system/capabilities/`. Inspect the component registry as the separate
catalog of implementation machinery. Run `CapabilityResolver` and preserve its
candidate comparison and resolution artifact.

Resolution order is:

1. `reuse` when one existing contract satisfies the request;
2. `compose` when compatible existing capabilities cover it together;
3. `extend` when the missing behavior belongs in one existing abstraction;
4. `new` only for a genuinely missing primitive.

Never override a resolver result by silently creating a near-duplicate. If the
result appears wrong, improve the manifest evidence or resolver contract and run
it again, preserving the earlier result as evidence.

## Gap, context, and research

Freeze `CapabilityBuildPlan` before implementation. Its missing requirements
define the research questions. Build minimum-sufficient context from the
selected capability manifests, component schemas, runtime contracts, relevant
architecture and policies, allowed dependencies, evaluation requirements, and
affected dependents. Expand context only when a recorded question requires it.

For each unresolved technical question, create a
`CapabilityResearchDecision`: alternatives, selected approach, rationale,
rejections, confidence, and sources. Do not return a general research essay.

## Build

Use `CapabilityDevelopmentService.scaffold`. Keep its fixed shell:

```text
capability.yaml
contract/input.schema.json
contract/output.schema.json
implementation/pipeline.yaml
implementation/custom/
tests/{contract,functional,integration,regression,fixtures}/
evaluation/eval.yaml
provenance/{resolution,build-plan,research-decisions}.yaml
README.md
```

Prefer configuration and composition. Put custom implementation only in the
declared custom area. Do not add dynamic imports to a manifest, execute proposal
data, mutate canonical datasets, or change shared registries during the build.

## Validate

Add executable tests and non-empty evaluation cases. Run focused tests, then the
repository quality checks appropriate to the change. Validate with
`CapabilityPackageValidator`; all checks must pass. Treat failures as evidence
and revise within the frozen plan or produce a new plan revision when scope or
architecture changes.

## Propose and register

Use `CapabilityRegistrar.propose` only after validation passes. Shared runtime
registration requires a matching approved `ApprovalRecord` with
`action_type=update_toolbox`. Project-local experimental execution additionally
requires the existing independent component-review and isolation path when the
package contains executable code. A proposal is not registration.

Return the capability ID/version, resolution, reused capabilities/components,
research-decision refs, package path, tests/evals run, validation ID/hash,
registration proposal ID, and any required approval.
