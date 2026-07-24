---
name: remote-execution
description: Use when an approved experiment plan requires remote compute to record an auditable run while keeping the local harness authoritative.
---

# Remote Execution

For an approved plan, prepare or record `remote_run_record.md` with project and experiment IDs, host profile, command, environment, start and end times, exit status, logs, artifact URIs, failure reason, retry guidance, and provenance.

Read `AGENTS.md`, `_architecture/09_REMOTE_EXECUTION.md`, and `_core/authority_boundaries.md`. Remote workers execute explicit bundles and never become sources of truth. Raw data transfer requires privacy and governance approval.

Follow `checklist.md`, validate the result against `output_contract.md`, and use only synthetic examples from `examples/` as guidance. Capture stdout and stderr and register returned logs and artifacts in local artifact memory.
