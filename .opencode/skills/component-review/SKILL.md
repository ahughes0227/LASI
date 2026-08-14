---
name: component-review
description: Review a requested LASI component for automatic project-scoped experimental approval or genuine security/stability escalation.
---

# Component Review

Read `AGENTS.md`, `_architecture/01_ARCHITECTURE.md`, `_architecture/04_EXPERIMENT_SYSTEM.md`, `_architecture/08_DECISION_SYSTEM.md`, and `_architecture/14_GOVERNANCE.md`. Inspect source and dependency evidence directly; do not rely only on the requesting agent's assertions.

Produce a typed `ComponentReview` using `services.components.ComponentReviewService`. Automatically approve only project-scoped experimental components with a verified immutable source hash, approved dependencies, strict configuration schema, typed outputs, passing tests, static handler binding, bounded resources, workdir confinement, enforced isolation, and no network, subprocess, external-provider, secret, native-code, or shared-state access.

Route missing tests, contracts, or other correctable stability evidence back for revision without human interruption. Escalate only genuine security or stability risk and shared toolbox promotion. Review does not execute code and project-scoped approval does not promote a component globally.
