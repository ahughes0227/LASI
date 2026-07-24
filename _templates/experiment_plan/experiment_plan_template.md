Experiment Plan Template
========================

Schema: _schemas/experiment_plan.schema.yaml

Example only. No experiment may run until a decision record exists.

```text
experiment_plan_id: PLAN-YYYY-0001
project_id: PROJECT-XXXX
ticket_id: TICKET-XXXX
dataset_version: DATASET:v1 or DATASET:v2
schema_version: "1.0"
hypothesis: |
    A short, testable hypothesis.
reason_for_experiment: |
    Why the experiment is needed and what it tests.
experiment_type: baseline_probe|learning_curve|embedding_or_cluster_analysis|error_analysis
planned_tool_runs:
    - tool_id: name
        run_id: RUN-0001
        inputs: list of inputs
execution_backend: local|remote
remote_host_profile: null or profile-id
expected_artifacts:
    - path/to/artifact
expected_signal: |
    What metric changes would indicate success
success_criteria: |
    Numeric or explicit pass/fail criteria
failure_criteria: |
    Numeric or explicit failure criteria
budget_estimate: {cost_usd: 0, cpu_hours: 0}
privacy_mode: local_only|summary_only_to_scientist|plots_allowed|thumbnails_allowed|raw_samples_allowed|knowledge_allowed
approval_required: false
decision_record_required: true
stop_condition: |
    Conditions under which the experiment should be aborted
handoff_after_decision: |
    Which team or workflow will receive artifacts after run
provenance:
    author: name <email>
    created_at: 2026-05-30T00:00:00Z
    source_records: [projects/PROJECT-XXXX/tickets/TICKET-XXXX.md]
    source_artifacts: []
```

Note: `decision_record_required` must be `true` and a decision recorded before any execution.
