Outcome Record Template
=======================

Example only. Use structured fields; distinguish validation vs production outcomes.

```
schema_version: "1.0"
project_id: PROJECT-XXXX
current_status: pending|research_only|validated_not_deployed|deployed|successful_in_production|failed_validation|failed_in_production|cancelled|abandoned|blocked|superseded|archived
final_disposition: brief text
deployment_status: not_deployed|staged|deployed|rolled_back|n/a
production_status: not_in_production|in_production|failed_in_production|n/a
reason_category: performance|privacy|budget|policy|other
result_summary: |
	Concise structured summary (metrics, comparisons, pass/fail against criteria)
cancellation_reason: null
failure_reason: null
blocked_reason: null
owner: name <email>
decision_date: YYYY-MM-DD or null
last_updated_at: 2026-05-30T00:00:00Z
related_reports:
  - path/to/static_report.md
related_artifacts:
  - path/to/report-artifact
follow_up_actions:
  - description of next action
```

Notes:
- `current_status` must be one of the allowed status values above.
- Distinguish `validated_not_deployed` from `successful_in_production` explicitly.
