Experiment Plan Template
========================

Schema: _schemas/experiment_plan.schema.yaml

Example only. No experiment may run until a decision record exists.

```text
experiment_plan_id: PLAN-YYYY-0001
project_id: PROJECT-XXXX
ticket_id: TICKET-XXXX
dataset_version: DATASET:v1 or DATASET:v2
hypothesis: |
    A short, testable hypothesis.
reason_for_experiment: |
    Why the experiment is needed and what it tests.
experiment_type: validation|benchmark|ablation|prototype
planned_tool_runs:
    - tool: name
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
privacy_mode: public|restricted|private
approval_required: yes|no
decision_record_required: yes
stop_condition: |
    Conditions under which the experiment should be aborted
handoff_after_decision: |
    Which team or workflow will receive artifacts after run
provenance:
    - ticket: TICKET-XXXX
    - created_by: name <email>
    - created_at: YYYY-MM-DD
```

Note: `decision_record_required` must be `yes` and a decision recorded before any execution.
