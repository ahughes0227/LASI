# Step 03 — Create Project Folder

Purpose
: Create the canonical project directory and baseline files.

Inputs

- Accepted ticket and basic metadata.

Expected output

- `projects/<project-id>/` containing `context.md`, `status.md`, `decisions.md`, `tasks.md`, and folders `inputs/`, `working/`, `artifacts/`, `outputs/`, `reports/`.

Actions

- Generate a stable `project_id` from ticket_id or provided project_id.
- Copy ticket into `projects/<id>/inputs/ticket.md`.
- Create `projects/<id>/status.md` with initial status `accepted`.

Stop / Escalation

- Unable to create project folder or missing authorization for requested scope.

Skill

- `project` (file ops), `decision-review` for any gating checks.
