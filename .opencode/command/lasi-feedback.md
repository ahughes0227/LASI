---
description: Give LASI human feedback on a pending escalation and continue.
agent: lasi-admin
---

Parse `$ARGUMENTS` as the assignment-or-project ID, exact pending escalation ID, and the user's feedback. Call `services.admin.open_admin_service().respond(...)` only when both IDs match the pending escalation. Preserve the feedback as a durable `escalation_answered` event and launch the detached worker after recording it. Never infer, rewrite, or manufacture the user's feedback. If no matching escalation is pending, report that without changing assignment state.
