---
description: Show durable LASI assignment state and recent progress.
agent: lasi-admin
---

Resolve the assignment ID or project ID in `$ARGUMENTS` with `services.admin.open_admin_service().status(...)`, then read recent `events(...)`. Report status, whether the worker lease is active, coordinator turns, latest summary, next wake time, plateau state when available, and any pending escalation. When an escalation is pending, include its exact ID, question, and the ready-to-copy syntax `/lasi-feedback <project-or-assignment> <escalation-id> <feedback>`. For `runtime_blocked`, report the precise infrastructure preflight failure and recommend resume only after it is corrected. For `budget_exhausted`, report which limit was reached and its observed value from the `assignment_budget_exhausted` event, and explain that continuing requires cancelling and starting a new assignment with an authorized budget rather than resuming. Do not wake or alter the assignment.
