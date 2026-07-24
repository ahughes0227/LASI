---
name: workflow-authoring
description: Use when creating or editing LASI `_workflows/**/STEP.md` files to preserve canonical headings, skill identifiers, blocking conditions, and handoffs.
---

# Workflow Authoring

Every `STEP.md` must use these case-sensitive headings in this order:

1. `Purpose`
2. `Inputs`
3. `Actions`
4. `Skill`
5. `Expected output`
6. `Stop / Escalation`
7. `Handoff`

Use short declarative lines. Avoid lowercase colon-only headings because workflow tooling may parse the canonical headings.

`Skill` must name one canonical hyphenated skill discoverable at `.opencode/skills/<skill>/SKILL.md`. `Expected output` must reference a template or artifact filename. `Stop / Escalation` must state conditions that prevent handoff to the next step.

Validate changed workflows for heading order, existing skill references, output contracts, authority boundaries, and decision gates before completion.
