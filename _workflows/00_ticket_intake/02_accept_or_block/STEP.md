# Step 02 — Accept or Block

Purpose
: Decide whether to accept, block, or request clarification for the ticket.

Inputs
- Ticket validation checklist from previous step.

Actions
- Apply governance and privacy checks.
- If high-consequence, convert to `human_review_required` with clear questions.

Skill
- decision-review

Expected output
- Ticket moved to `tickets/accepted` or `tickets/blocked` or `tickets/human_review_required`.
- If accepted, a starter `projects/<id>/decisions.md` entry noting acceptance.

Stop / Escalation
- Any work requiring dataset changes, remote execution, or label edits must not proceed without a decision record.

Handoff
- Move accepted tickets into `tickets/accepted` and create project folder per `03_create_project_folder`.
