Step: 04 Plan Experiments
=========================

Purpose
Create an ordered experiment plan targeting identified issues.

Inputs
- `dataset_characterization.md`

Actions
1. Run `experiment-planning` skill checklist.
2. Produce `experiment_plan.md` with priorities and stop/success conditions.

Skill
- experiment-planning

Expected output
- `experiment_plan.md`

Stop / Escalation
- If experiments require unavailable resources, annotate and escalate to `05_decision_review`.

Handoff
- Pass plan to `05_run_experiments`.
