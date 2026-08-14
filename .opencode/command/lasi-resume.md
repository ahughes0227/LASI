---
description: Resume a paused or interrupted LASI assignment.
agent: lasi-admin
---

Resume the assignment ID or project ID in `$ARGUMENTS` with `services.admin.open_admin_service().resume(...)`. The service must pass its OpenCode CLI preflight before changing durable state. Launch the detached worker and report the assignment ID and new state. This includes recovery from `runtime_blocked`; do not perform the research loop inline.
