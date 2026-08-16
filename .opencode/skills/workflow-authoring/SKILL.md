---
name: workflow-authoring
description: Use when creating or editing LASI `_workflows/**/workflow.json` packages and their versioned prompt, rubric, and profile assets.
---

# Workflow Authoring

Workflow authority lives in `_workflows/<workflow_id>/workflow.json`. OpenCode skill Markdown is procedural guidance only. Every node declares identity, dependencies, typed artifact reads/writes, activation and skip policy, versioned prompt/rubric references, a canonical skill/capability binding, and decision bindings where required.

Use `services.workflows.WorkflowLoader` to validate graph correctness, references, authority boundaries, and decision gates. Execution nodes must reference persisted plans and allowing decisions. Never create `STEP.md` files or reproduce routing logic in agent prompts.
