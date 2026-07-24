Example only. Not real project data.

```
outcome_id: OUT-EX-0001
project_id: PROJECT-EX1
ticket_id: TICKET-0001
current_status: validated_not_deployed
previous_status: pending
new_status: validated_not_deployed
outcome_event_type: validation_result
final_disposition: validation passed for nighttime AP
deployment_status: not_deployed
production_status: not_in_production
reason_category: performance
result_summary: |
  Nighttime AP increased by 5.2% vs parent. No regressions observed.
evidence:
  - projects/PROJECT-EX1/reports/validation_results.md
related_decision: DEC-EX-0001
owner: alice@example.com
created_at: 2026-05-30
follow_up_actions:
  - action: label audit for nighttime subset
    owner: data-owner@example.com
    due: 2026-06-07
knowledge_proposal_needed: no
```
