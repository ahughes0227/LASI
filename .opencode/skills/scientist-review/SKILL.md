---
name: scientist-review
description: Use after experiments produce diagnostic packets to analyze evidence and draft a provider-neutral ScientistReview without authorizing actions.
---

# Scientist Review

Use a mock or real provider to analyze experiment results and produce `scientist_review.md` with observations, graded confidence, ranked recommendations, referenced artifacts, and provenance.

Read `AGENTS.md` and `_architecture/07_SCIENTIST_PROVIDER.md` first. Required inputs are diagnostic artifacts and `experiment_plan.md`. Scientists must not change data, run tools, or authorize actions. The review is a recommendation, not a decision.

Normalize provider inputs, validate the resulting schema, and flag urgent findings without granting them authority. Follow `checklist.md`, validate against `output_contract.md`, and use `examples/` only as synthetic guidance.
