# Step 05 — Handoff to Requested Workflow

Purpose
: Route the initialized project into the requested workflow and record handoff details.

Inputs

- `projects/<id>/requested_workflow` or ticket's `requested_workflow` field.

Expected output

- Ticket moved to `tickets/running` and a handoff note in `projects/<id>/decisions.md` describing target workflow and entry step.

Actions

- Verify requested workflow exists under `_workflows/`.
- Create `projects/<id>/handoff.md` with `from_ticket`, `to_workflow`, `entry_step`, and `handed_off_by`.

Stop / Escalation

- Requested workflow missing → move ticket to `tickets/blocked` and create a proposal to add the workflow.

Skill

- `decision-review`, `project`
