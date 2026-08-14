---
description: Cancel a LASI assignment without discarding its history.
agent: lasi-admin
---

Cancel the assignment ID or project ID in `$ARGUMENTS` with `services.admin.open_admin_service().cancel(...)`. Preserve all events and artifacts. Report `cancelling` until the current atomic turn checkpoints, or `cancelled` when no worker is active. Cancellation is not deletion.
