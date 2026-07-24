Remote Run Output Contract
==========================

Produces `remote_run_record.md` with fields:

- project_id
- experiment_id
- host_profile
- command
- start_time / end_time
- exit_code
- logs_uri
- artifacts: list of URIs
- provenance

On failure, include structured failure reason and whether retry is suggested.
