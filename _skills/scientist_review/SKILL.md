Skill: Scientist Review
=======================

Purpose
-------

Use a provider (mock or real) to analyze experiment results and produce a `ScientistReview` artifact with rationale and recommended next steps.

When to use
-----------

After experiments finish and diagnostic packets are available.

Required inputs
---------------

- Diagnostic artifacts and `experiment_plan.md`.

Required outputs
----------------

- `scientist_review.md` (normalized contract) saved under project artifacts.

Files to read first
-------------------

- _core/authority_boundaries.md
- _architecture/07_SCIENTIST_PROVIDER.md

Forbidden actions
-----------------

- Scientists MUST NOT change data, run tools, or authorize actions.

Completion criteria
-------------------

- `scientist_review.md` contains observations, graded confidence, and actionable recommendations with provenance.
