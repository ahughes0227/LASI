# Step 01 — Review Ticket

Purpose
: Read the ticket and validate required fields.

Inputs

- Ticket file from `tickets/inbox`.

Expected output

- Validation checklist saved to `projects/<id>/inputs/ticket_validation.md` or ticket moved to `tickets/blocked`.

Actions

- Verify required structured fields are present.
- Check privacy_mode, dataset references, and governance flags.
- Collect missing info requests and assign `human_review_contact`.

Stop / Escalation

- Missing essential fields → move ticket to `tickets/blocked` with notes.

Skill

- `dataset_intake` (if dataset referenced)
- `decision_review` (for governance checks)
