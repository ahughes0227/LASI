# Static Report Outline

Schema: `_schemas/static_report.schema.yaml`

This is an authored example of `StaticReportData`. Every fixed section is present,
including sections that were not run or were deferred. Recommendations remain
separate from the decision record.

Allowed `section_status` values:

- `complete`
- `not_run`
- `not_available`
- `not_applicable`
- `blocked_by_privacy`
- `blocked_by_policy`
- `blocked_by_budget`
- `failed`
- `partial_success`
- `deferred_to_later_phase`

```yaml
schema_version: "1.0"
report_id: REPORT-YYYY-0001
report_header:
  title: Report Title
  project_id: PROJECT-XXXX
  date: 2026-05-30

executive_summary: &section
  section_status: complete
  source_records: []
  source_artifacts: []
  summary: One-paragraph summary.
  missing_or_blocked_reason: null
  content: {}
current_decision: *section
dataset_summary: *section
dataset_characterization: *section
experiment_summary: *section
model_comparison: *section
performance_gap_diagnosis: *section
learning_curves:
  section_status: deferred_to_later_phase
  source_records: []
  source_artifacts: []
  summary: null
  missing_or_blocked_reason: Learning-curve evidence was deferred.
  content: {}
error_analysis: *section
cluster_or_latent_analysis: *section
scientist_review: *section
decision_record: *section
knowledge_context: *section
recommendation: *section
project_outcome: *section
appendix: *section
project_outcome_status: pending
provenance:
  author: analyst@example.com
  created_at: "2026-05-30T00:00:00Z"
  source_path: projects/PROJECT-XXXX/reports/static_report_data.yaml
  source_records: []
  source_artifacts: []
report_state: generated
```

`source_records` and `source_artifacts` entries should identify the records and
artifacts used to populate each section.
