---
description: Checkpoint and pause a running LASI assignment safely.
agent: lasi-admin
---

Pause the assignment ID or project ID in `$ARGUMENTS` with `services.admin.open_admin_service().pause(...)`. Report `pausing` while the current atomic coordinator turn is still finishing. The computer is safe to shut down only after a later `/lasi-status` reports `paused`; preserve all durable state for `/lasi-resume`.
