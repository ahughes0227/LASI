# Dataset Update Validation Workflow

goal
: Answer whether a dataset update solved the intended problem and whether the child dataset is comparable to its parent.

when to use it
: When a dataset update proposal or candidate new version is available and requires validation before promotion.

required inputs
- Parent and child dataset manifests and characterizations
- Update proposal and change log
- Evaluation preference and benchmarks

operating surface
- Start and resume this workflow through OpenCode commands or the LASI coordinator.
- OpenCode specialist agents invoke the named skills; reusable Python services are the implementation layer when available.
- Approval and handoff rules remain authoritative regardless of how the workflow is invoked.
- Skill procedures are available under `.opencode/skills/`.

ordered steps
- 01_review_update_proposal
- 02_validate_parent_and_child_versions
- 03_compare_characterizations
- 04_plan_validation_experiments
- 05_decision_review
- 06_run_validation_experiments
- 07_compare_results
- 08_update_dataset_portfolio
- 09_generate_update_report
- 10_record_outcome

skills used
- `dataset-characterization`, `experiment-planning`, `decision-review`, `report-generation`

expected outputs
- Experiment plan(s) for validation
- Decision record authorizing or blocking promotion
- Static update report with sectioned statuses
- Outcome record

approval points
- Label changes, dataset promotion, benchmark changes, non-comparable findings, remote execution, or expensive runs must be gated by decision records.

stop conditions
- Non-comparable datasets without remediation plan
- Privacy or policy blocks
- Budget or compute constraints

handoff rules
- Decision record must specify allowed execution backend (`local` or `remote`) and any `remote_host_profile` when allowed.
- If allowed, experiments proceed under `projects/<id>/working/` and `projects/<id>/artifacts/`.
