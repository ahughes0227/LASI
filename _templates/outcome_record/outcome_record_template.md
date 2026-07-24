Outcome Record Template
=======================

Example only. Use structured fields; distinguish validation vs production outcomes.

```
outcome_id: OUT-YYYY-0001
project_id: PROJECT-XXXX
ticket_id: TICKET-XXXX
current_status: pending|research_only|validated_not_deployed|deployed|successful_in_production|failed_validation|failed_in_production|cancelled|abandoned|blocked|superseded|archived
previous_status: |
new_status: |
outcome_event_type: e.g., validation_result|deployment|cancel|supersede
final_disposition: brief text
deployment_status: not_deployed|staged|deployed|rolled_back|n/a
production_status: not_in_production|in_production|failed_in_production|n/a
reason_category: performance|privacy|budget|policy|other
result_summary: |
	Concise structured summary (metrics, comparisons, pass/fail against criteria)
evidence:
	- path/to/report.md
related_report: path/to/static_report.md
related_decision: DEC-YYYY-0001
related_experiments:
	- EXP-YYYY-0001
owner: name <email>
created_at: YYYY-MM-DD
follow_up_actions:
	- action: description
		owner: name
		due: YYYY-MM-DD
knowledge_proposal_needed: yes|no
```

Notes:
- `current_status` must be one of the allowed status values above.
- Distinguish `validated_not_deployed` from `successful_in_production` explicitly.
