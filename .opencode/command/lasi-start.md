---
description: Start a durable autonomous LASI assignment.
agent: lasi-admin
---

Start the assignment described by `$ARGUMENTS` through `services.admin.open_admin_service().start(...)`. Require a project ID and objective; infer a project name only when unambiguous. Build a typed `ResearchLoopPolicy`, defaulting plateau patience to 4 and requiring increasingly novel valid attempts. The same policy carries the assignment's turn cap and token ceiling; keep the defaults unless the user states a budget, and report the values you used. The service must pass its OpenCode CLI preflight before it creates the assignment. Launch the detached worker. Return the assignment ID and status, then stop; do not perform research inline.
