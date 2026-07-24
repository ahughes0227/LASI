# Ticket Intake Workflow

goal
: Convert a ticket from `tickets/inbox` into a new project scaffolding or block/route the ticket.

when to use it
: For any incoming project initiation request in `tickets/inbox` that proposes work for LASI.

required inputs

- A filled ticket file in `tickets/inbox` (see ticket template)
- Contact for the ticket creator (`human_review_contact`)

operating surface

- Start this workflow from the LASI OpenCode coordinator or the relevant OpenCode command.
- The coordinator delegates bounded steps to specialist agents and skills; reusable Python services, when implemented, perform the underlying work.
- Do not invoke an ad hoc LASI application CLI or bypass the decision and governance handoffs below.
- Canonical skill procedures are available only under `.opencode/skills/`, including `dataset-intake`, `decision-review`, and `experiment-planning`.
- The available commands do not form a general workflow router. The coordinator or specialist agent must interpret the requested workflow and handoff; this procedure does not imply that a command automatically executes every referenced step.

ordered steps

- 01_review_ticket
- 02_accept_or_block
- 03_create_project_folder
- 04_initialize_project_files
- 05_handoff_to_requested_workflow

skills used

- `dataset-intake` (when ticket references datasets)
- `decision-review` (to block/accept)
- `experiment-planning` (to create initial plan placeholder)

expected outputs

- Project folder under `projects/<project-id>/` with required files
- `projects/<project-id>/inputs/` populated with ticket and metadata
- A decision or status record placed in `projects/<project-id>/decisions.md` or ticket moved to `tickets/blocked`/`tickets/accepted`

stop conditions

- Ticket lacks required fields (move to `tickets/blocked`)
- Privacy or governance block detected (block and escalate)

approval points

- Any proposed dataset changes, remote execution, label-policy edits require an explicit decision record before work proceeds.

handoff rules

- After initialization, move the ticket to `tickets/accepted` and create a `tasks.md` entry.
- If the ticket requests a specific workflow (e.g., `dataset_update_validation`), create a pointer file `projects/<id>/requested_workflow` and move the ticket to `tickets/running`.
