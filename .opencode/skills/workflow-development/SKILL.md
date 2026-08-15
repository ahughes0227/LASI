---
name: workflow-development
description: Use when resolving, researching, building, validating, or proposing registration of a LASI workflow package.
---

# Workflow Development

Use this lifecycle exactly:

```text
SPECIFY → RESOLVE → GAP → CONTEXT → RESEARCH → PLAN → BUILD → VALIDATE → PROPOSE
```

Translate intent once into `WorkflowDefinition`. Resolve structurally through
`WorkflowResolver` before researching or authoring. Accept only REUSE, COMPOSE,
EXTEND, or NEW. Freeze a `WorkflowBuildPlan`; research only recorded gaps.

Build only through `WorkflowDevelopmentService.scaffold`, which creates the
fixed workflow package shell. Validate with `WorkflowPackageValidator`; it must
pass graph, binding, test, evaluation, and provenance checks before
`WorkflowRegistrar.propose` may create a registration proposal.

Workflow JSON is the control-plane authority. Prompts, rubrics, and profiles are
versioned bindings. OpenCode skills remain procedural guidance and must not
duplicate graph routing. A proposal is not installation or authorization.
