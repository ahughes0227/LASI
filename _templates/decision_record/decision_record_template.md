Decision Record Template
=========================

Schema: _schemas/decision_record.schema.yaml

Example only. Use the canonical decision fields defined in the schema and provide explicit rationale.

```text
schema_version: "1.0"
decision_id: DEC-YYYY-0001
project_id: PROJECT-XXXX
recommendation_id: optional-recommendation-id
experiment_plan_id: optional-plan-id
decision_type: operational|policy|budget|security|other
risk_level: low|medium|high|critical
action_requested: describe requested action
decision: allow|allow_with_warning|block|escalate_for_approval|convert_to_proposal|request_clarification|stop_project|defer
allowed: true|false
approval_required: false
approved_by: name <email> or null
approval_date: YYYY-MM-DD or null
approval_expiration: YYYY-MM-DD or null
blocked_by: []
missing_inputs: []
policy_checks: summary
privacy_checks: summary
budget_checks: summary
remote_execution_checks: summary
rationale: |
    Provide a concise, explicit rationale tying evidence to decision. Include metrics, thresholds, and alternatives considered.
conditions:
    - Explicit conditions or mitigations attached to an `allow_with_warning` decision.
next_action: |
    Clear, actionable next steps and owners.
handoff_target: local|remote|team-name OR null
created_at: 2026-05-30T00:00:00Z
provenance:
  author: name <email>
  created_at: 2026-05-30T00:00:00Z
  source_records: [projects/PROJECT-XXXX/tickets/TICKET-XXXX.md]
  source_artifacts: [projects/PROJECT-XXXX/artifacts/static_report.md]
```

Notes:

- This template references the canonical schema at `_schemas/decision_record.schema.yaml`.
- `decision` must be one of the allowed values above. `rationale` must include numeric thresholds or concrete comparison points when applicable.
