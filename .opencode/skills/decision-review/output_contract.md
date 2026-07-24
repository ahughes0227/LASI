# Decision Record Output Contract

`decision_record.md` contains:

- Decision ID, project ID, recommendation ID, and experiment-plan ID when applicable
- Requested action
- Decision: `allow`, `allow_with_warning`, `block`, `escalate_for_approval`, `convert_to_proposal`, `request_clarification`, `stop_project`, or `defer`
- Allowed state
- Decision type and risk level
- Explicit rationale with numeric thresholds when applicable
- Approval requirement, approver, approval date, and expiration
- Blocked items and missing inputs
- Policy, privacy, budget, tool, comparability, and remote-execution checks
- Conditions and mitigations
- Actionable next steps, owners, and handoff target
- Provenance with author, creation time, source records, and source artifacts

The record must conform to `_schemas/decision_record.schema.yaml` and `_templates/decision_record/decision_record_template.md`.
