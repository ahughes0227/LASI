---
description: Run the governed dataset diagnostic workflow from intake through report and outcome handoff.
agent: lasi-coordinator
---

Route `$ARGUMENTS` through the dataset diagnostic workflow. Use the implemented dataset, experiment, decision, tool, provider, report, and outcome services where available. Do not execute experiments until the plan has a recorded allowed decision; stop explicitly on blocked, failed, partial, or missing handoffs.
