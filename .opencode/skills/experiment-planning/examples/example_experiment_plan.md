Example only. Not real project data.

```
experiment_plan_id: PLAN-EX-0001
project_id: PROJECT-EX1
ticket_id: TICKET-0001
dataset_version: ExampleImageSet:v2
hypothesis: Adding 10k nighttime images will raise nighttime AP by >= 5% relative to v1.
experiment_type: validation
planned_tool_runs:
  - tool: image-eval
    run_id: RUN-EX-0001
execution_backend: local
expected_artifacts:
  - projects/PROJECT-EX1/artifacts/nighttime_eval/results.csv
expected_signal: nighttime AP delta >= 0.05
success_criteria: nighttime AP delta >= 0.05 and no overall AP regression > 1%
failure_criteria: nighttime AP delta < 0.02 or overall AP regression > 2%
budget_estimate: {cost_usd: 120, cpu_hours: 12}
decision_record_required: yes
```
