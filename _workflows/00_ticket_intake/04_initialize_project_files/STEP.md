# Step 04 — Initialize Project Files

Purpose
: Populate initial placeholders for work: context, tasks, and requested_workflow pointer.

Inputs

- Project folder with ticket.

Expected output

- `projects/<id>/context.md`, `tasks.md`, `decisions.md`, and an empty `working/` and `artifacts/`.

Actions

- Create `context.md` from ticket fields (project summary, dataset refs, contacts).
- Add starter task list in `tasks.md` with owner and due dates.
- If the ticket requested a workflow, write `requested_workflow` file.

Stop / Escalation

- Missing essential contact or privacy info.

Skill

- `project`, `experiment-planning` (starter plan placeholder)
