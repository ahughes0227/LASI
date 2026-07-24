Skill: Remote Execution
=======================

Purpose
-------

Run approved experiment tasks on remote hosts, collect logs and artifacts, and record provenance.

When to use
-----------

When an `experiment_plan` requires remote compute resources.

Required inputs
---------------

- Approved `experiment_plan.md` and `Decision Record` if required.
- Remote host profile and credentials (handled by infra, not the agent).

Required outputs
----------------

- `remote_run_record.md` with host profile, command, logs, artifacts, and exit status.

Files to read first
-------------------

- _architecture/09_REMOTE_EXECUTION.md
- _core/authority_boundaries.md

Forbidden actions
-----------------

- Do not assume remote host is authoritative; local harness remains source of truth.

Completion criteria
-------------------

- Remote run record saved with logs and artifact URIs, or a structured failure reason.
