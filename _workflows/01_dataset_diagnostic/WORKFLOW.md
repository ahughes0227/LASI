Workflow: Dataset Diagnostic (MVP)
================================

Goal
----

Identify why model performance is limited for a dataset and produce a fixed static report and decisions.

When to use
-----------

When a project seeks to diagnose dataset or labelling issues that limit performance.

Required inputs
---------------

- Raw dataset or `dataset_manifest.md`
- Project objectives and target metric

Operating surface
------------------

Start and resume this workflow through OpenCode. OpenCode commands select the relevant specialist agent, and that agent invokes the canonical hyphenated skill for each step. Skills are procedural guidance, not authority; implementation should delegate to reusable Python services when available. No direct LASI application CLI is required. All skill procedures, contracts, checklists, and examples are under `.opencode/skills/`. The current command surface does not automatically execute this workflow or provide a general runner for all `_workflows/**` steps, so routing and handoffs remain coordinator/agent responsibilities.

Ordered steps
-------------

1. Intake: `_workflows/01_dataset_diagnostic/01_intake/STEP.md` (skill: `dataset-intake`)
2. Validate dataset: `02_validate_dataset/STEP.md` (skill: `dataset-characterization`)
3. Characterize dataset: `03_characterize_dataset/STEP.md` (skill: `dataset-characterization`)
4. Plan experiments: `04_plan_experiments/STEP.md` (skill: `experiment-planning`)
5. Scientist review: `06_scientist_review/STEP.md` (skill: `scientist-review`)
6. Decision review: `07_decision_review/STEP.md` (skill: `decision-review`)
7. Run experiments: `05_run_experiments/STEP.md` (skill: `remote-execution`)
8. Generate report: `08_generate_report/STEP.md` (skill: `report-generation`)
9. Record outcome: `09_record_outcome/STEP.md` (skill: `outcome-recording`)

Skills used
-----------

`dataset-intake`, `dataset-characterization`, `experiment-planning`, `remote-execution`, `scientist-review`, `decision-review`, `report-generation`, `outcome-recording`

Expected outputs
----------------

- dataset_manifest.md
- dataset_characterization.md
- experiment_plan.md
- remote_run_record(s)
- scientist_review.md
- decision_record.md
- static_report
- outcome_record.md

Human approval points
---------------------

- Before `05_run_experiments` if experiments require high-cost resources.
- Decision review before any high-consequence dataset or label changes.

Decision-to-execution handoff
-----------------------------

Execution may only proceed after a recorded decision. The required handoff sequence is:

1. `scientist-review` produces `scientist_review.md` with recommendations.
2. `experiment_plan` is authored and linked to the scientist review.
3. A `decision_record` is created and must have `decision` in `[allow, allow_with_warning]` to permit execution.
4. The decision record must state `execution_backend` (local or remote) and include a `remote_host_profile` when remote execution is allowed.

If the decision is `block`, `defer`, `request_clarification`, `stop_project`, or `escalate_for_approval` without approval, no execution may occur.

Stop conditions
---------------

- Missing input manifests
- Failure to produce key artifacts (manifest, characterization)
