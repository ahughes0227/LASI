Step: 06 Scientist Review
=========================

Purpose
-------

Have a scientist provider analyze experiment results and recommend next steps.

Inputs
------

- diagnostic packets and `experiment_plan.md`

Actions
-------

1. Run `scientist-review` skill checklist to create `scientist_review.md`.

Skill
-----

scientist-review

Expected output
---------------

- `scientist_review.md` with observations and ranked recommendations.

Stop / Escalation
-----------------

- If recommendations require high-consequence changes, escalate to `decision-review`.

Handoff
-------

Pass review to `07_decision_review`.
