Decision Record Output Contract
================================

`decision_record.md` fields (canonical):

- decision_id
- project_id
- ticket_id (optional)
- decision: one of [allow, allow_with_warning, block, escalate_for_approval, convert_to_proposal, request_clarification, stop_project, defer]
- allowed: boolean
- decision_type: operational|policy|budget|security|other
- risk_level: low|medium|high|critical
- rationale: explicit, include numeric thresholds when applicable
- approved_by: name <email> or null
- approval_date: YYYY-MM-DD or null
- approval_expiration: YYYY-MM-DD or null
- blocked_by: list
- missing_inputs: list
- policy_checks, privacy_checks, budget_checks, remote_execution_checks: summaries
- conditions: mitigation text (when allow_with_warning)
- next_action: actionable next steps and owners
- handoff_target: team or workflow
- provenance: author, created_at, referenced_artifacts

Notes:
- This contract matches `_schemas/decision_record.schema.yaml` and `_templates/decision_record/decision_record_template.md`.
