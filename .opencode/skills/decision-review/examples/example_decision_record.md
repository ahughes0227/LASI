Example only. Not real project data.

```
decision_id: DEC-EX-0001
project_id: PROJECT-EX1
decision_type: operational
risk_level: medium
action_requested: Run validation experiments PLAN-EX-0001
decision: allow_with_warning
approved_by: lead@example.com
approval_date: 2026-05-30
approval_expiration: 2026-06-30
rationale: |
  Evidence suggests nighttime augmentation will improve nighttime AP by ~5%. Approve experiments limited to 12 CPU hours and cost <= $200.
conditions: |
  Do not promote dataset without passing success criteria and additional label audit.
next_action: Run PLAN-EX-0001 and report results.
```
